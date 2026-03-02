# 09 — Full Execution Pipeline

## Pipeline Overview

```
Upload → Validate → Native Extract → OCR (if needed) → Chunk → Embed →
Classify → Select Template → Fill Card → Score → Save → [User: Edit/Regenerate] → Update
```

---

## Step-by-Step Pipeline

### STEP 1: Upload & Validate (SYNC — <500ms)

```python
async def step_1_upload(file: UploadFile, user_id: str) -> Document:
    """Validate and store uploaded PDF."""

    # 1a. Validate file type and size
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files accepted")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(400, "File exceeds 25MB limit")

    # 1b. Compute file hash for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # 1c. Check if already processed (cache hit!)
    existing = await db.get_document_by_hash(user_id, file_hash)
    if existing:
        return existing  # Return cached result immediately ← HUGE cost saving

    # 1d. Save file to storage
    storage_path = await storage.save_pdf(content, user_id, file.filename)

    # 1e. Create database record
    document = Document(
        user_id=user_id,
        original_filename=file.filename,
        file_hash=file_hash,
        file_size_bytes=len(content),
        storage_path=storage_path,
        status="uploaded",
    )
    await db.save(document)

    # 1f. Queue async processing
    pipeline_task.delay(document.id)

    return document  # Return immediately, processing continues async
```

**Cache point:** Duplicate file detection via hash

---

### STEP 2: PDF → Images + Native Text (ASYNC — 2-30s)

```python
@celery_app.task(queue="ocr_high")
def step_2_convert_and_extract(document_id: str):
    """Convert PDF pages to images AND extract native text."""

    document = db.get_document(document_id)
    pdf_path = storage.get_path(document.storage_path)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    pages = []
    for page_num in range(total_pages):
        page = doc[page_num]

        # 2a. Extract native text (FREE)
        native_text = page.get_text("text")
        has_native = len(native_text.strip()) > 50

        # 2b. Convert to image (needed for Gemini OCR or preview)
        dpi = select_dpi(page, has_native)  # Adaptive DPI
        image_path = convert_page_to_image(pdf_path, page_num, dpi)

        # 2c. Compute page hash for OCR caching
        pixmap = page.get_pixmap(dpi=72)
        image_hash = hashlib.sha256(pixmap.tobytes()).hexdigest()[:16]

        page_record = Page(
            document_id=document_id,
            page_number=page_num + 1,
            image_path=image_path,
            image_hash=image_hash,
            has_native_text=has_native,
            native_text_length=len(native_text),
            dpi=dpi,
        )
        pages.append((page_record, native_text))

    doc.close()

    # Save all pages
    db.bulk_save_pages([p[0] for p in pages])

    # Update document
    db.update_document(document_id, total_pages=total_pages, status="pages_converted")

    # Notify frontend
    ws_publish(document_id, {"step": "convert", "status": "complete", "pages": total_pages})

    # Chain to OCR step
    step_3_ocr.delay(document_id, [(p[0].id, p[1]) for p in pages])
```

**Cache point:** Image hash computed for OCR caching

---

### STEP 3: OCR (ASYNC — 2-5s per page)

```python
@celery_app.task(queue="ocr_high")
def step_3_ocr(document_id: str, pages_data: list):
    """OCR each page — hybrid: native → cache → Gemini."""

    results = []
    total_cost = 0.0

    for page_id, native_text in pages_data:
        page = db.get_page(page_id)

        # 3a. Try native text (FREE)
        if page.has_native_text and len(native_text) > 50:
            result = OCRResult(
                page_id=page_id,
                document_id=document_id,
                raw_text=native_text,
                ocr_method="native",
                ocr_confidence=0.95,
                api_cost_usd=0,
            )
            results.append(result)
            ws_publish(document_id, {
                "step": "ocr", "page": page.page_number, "method": "native", "cost": 0
            })
            continue

        # 3b. Check OCR cache (FREE)
        cached = cache.get_ocr_result(page.image_hash)
        if cached:
            result = OCRResult(
                page_id=page_id,
                document_id=document_id,
                raw_text=cached["text"],
                structured_json=cached.get("json"),
                ocr_method="cached",
                ocr_confidence=0.90,
                api_cost_usd=0,
                cache_key=page.image_hash,
            )
            results.append(result)
            ws_publish(document_id, {
                "step": "ocr", "page": page.page_number, "method": "cached", "cost": 0
            })
            continue

        # 3c. Gemini OCR (COSTS MONEY)
        ocr_text, tokens_used = gemini_ocr(page.image_path)
        cost = estimate_cost(tokens_used)
        total_cost += cost

        # Cache the result
        cache.set_ocr_result(page.image_hash, {
            "text": ocr_text,
            "json": parse_json_safe(ocr_text),
        })

        result = OCRResult(
            page_id=page_id,
            document_id=document_id,
            raw_text=ocr_text,
            structured_json=parse_json_safe(ocr_text),
            ocr_method="gemini_2.5_flash",
            model_used="gemini-2.5-flash",
            ocr_confidence=0.85,
            input_tokens=tokens_used["input"],
            output_tokens=tokens_used["output"],
            api_cost_usd=cost,
            cache_key=page.image_hash,
        )
        results.append(result)

        ws_publish(document_id, {
            "step": "ocr", "page": page.page_number, "method": "gemini", "cost": cost
        })

    # Save all OCR results
    db.bulk_save_ocr(results)
    db.update_document(document_id, status="ocr_complete")

    # Track API cost
    log_api_usage(document_id, total_cost)

    # Chain to chunking
    step_4_chunk.delay(document_id)
```

**Cache point:** OCR results cached by page image hash

**Validation point:** Check if OCR output is valid JSON

---

### STEP 4: Chunking (ASYNC — <2s)

```python
@celery_app.task(queue="embed_medium")
def step_4_chunk(document_id: str):
    """Chunk all OCR results into semantic segments."""

    ocr_results = db.get_ocr_results(document_id)
    chunker = SemanticChunker()

    all_chunks = chunker.chunk_document(
        ocr_pages=[{
            "page_number": r.page.page_number,
            "text": r.raw_text,
            "json": r.structured_json,
        } for r in ocr_results],
        document_id=document_id,
    )

    db.bulk_save_chunks(all_chunks)

    ws_publish(document_id, {
        "step": "chunk", "status": "complete", "total_chunks": len(all_chunks)
    })

    # Chain to embedding
    step_5_embed.delay(document_id, [c.id for c in all_chunks])
```

---

### STEP 5: Embedding (ASYNC — 1-5s)

```python
@celery_app.task(queue="embed_medium")
def step_5_embed(document_id: str, chunk_ids: list):
    """Generate embeddings and store in vector DB."""

    chunks = db.get_chunks(chunk_ids)
    embedding_service = EmbeddingService()

    # Batch embed (efficient)
    embedded_chunks = embedding_service.embed_chunks(chunks)

    # Store in ChromaDB
    vector_repo.store_chunks([{
        "chunk_id": c.id,
        "document_id": document_id,
        "content": c.content,
        "embedding": c.embedding,
        "page_number": c.page_number,
        "chunk_type": c.chunk_type,
        "metadata": c.metadata,
    } for c in embedded_chunks])

    # Save embedding references in PostgreSQL
    db.bulk_save_embeddings(embedded_chunks)

    ws_publish(document_id, {
        "step": "embed", "status": "complete", "chunks_embedded": len(embedded_chunks)
    })

    # Chain to classification + card generation
    step_6_classify_and_fill.delay(document_id)
```

---

### STEP 6: Classify Document Type + Generate Card (ASYNC — 2-5s)

```python
@celery_app.task(queue="embed_medium")
def step_6_classify_and_fill(document_id: str):
    """Classify document type, select template, fill card fields."""

    # 6a. Get document text summary (page-level chunks)
    page_chunks = db.get_chunks(document_id, level=1)
    doc_text = "\n".join(c.content[:500] for c in page_chunks[:3])  # First 3 pages

    # 6b. Classify document type
    doc_type, type_confidence = classify_document(doc_text)
    db.update_document(document_id, detected_type=doc_type, type_confidence=type_confidence)

    # 6c. Select matching template
    template = select_template(doc_type)

    # 6d. Create template card
    card = TemplateCard(
        document_id=document_id,
        user_id=db.get_document(document_id).user_id,
        template_id=template["id"],
        template_name=template["name"],
        status="draft",
    )
    db.save(card)

    # 6e. Fill each field
    for section in template["sections"]:
        field_value, method_used = extract_field_value(
            document_id=document_id,
            field_id=section["section_id"],
            field_type=section["type"],
        )

        card_field = CardField(
            card_id=card.id,
            field_id=section["section_id"],
            field_type=section["type"],
            section_id=section["section_id"],
            current_value=field_value,
            source_type=method_used,
            is_editable=section.get("editable", True),
            is_regeneratable=section.get("regeneratable", False),
        )
        db.save(card_field)

    db.update_card(card.id, status="auto_filled")

    # Chain to scoring
    step_7_score.delay(card.id)


def extract_field_value(document_id: str, field_id: str, field_type: str) -> tuple:
    """Extract a field value using cheapest available method."""

    # Strategy 1: Rule-based extraction (FREE)
    rule_extractor = RuleBasedExtractor()
    if rule_extractor.can_handle(field_type):
        all_text = db.get_document_text(document_id)
        results = rule_extractor.extract_all(all_text)

        field_key_map = {
            "issue_date": "date_english",
            "effective_date": "date_english",
            "deadline_alert": "date_english",
        }

        target_key = field_key_map.get(field_id)
        if target_key and target_key in results:
            return results[target_key][0], "rule_based"

    # Strategy 2: Vector search + small LLM
    query = field_id.replace("_", " ")
    query_embedding = embedding_service.embed_query(query)
    relevant_chunks = vector_repo.query_for_field(
        query_embedding=query_embedding,
        document_id=document_id,
        field_type=field_type,
        top_k=3,
    )

    context = "\n".join(c["content"] for c in relevant_chunks)

    # Use cheapest model that can handle this
    model = model_router.select_model("fill_field", "simple")

    prompt = f'Extract "{field_id}" from:\n{context}\nReturn only the value.'
    value = llm_service.generate(model["model"], prompt)

    return value, "ai_extraction"
```

**Validation point:** Document type classification confidence check

---

### STEP 7: Scoring (ASYNC — <1s)

```python
@celery_app.task(queue="score_low")
def step_7_score(card_id: str):
    """Score all fields and compute document-level confidence."""

    card = db.get_card(card_id)
    fields = db.get_card_fields(card_id)
    scorer = ConfidenceScorer()

    field_scores = []
    all_field_values = {f.field_id: f.current_value for f in fields}

    for field in fields:
        chunks = get_source_chunks(field)

        score = scorer.score_field(
            field_id=field.field_id,
            field_type=field.field_type,
            extracted_value=field.current_value,
            ocr_method=field.source_type,
            source_chunks=chunks,
            all_fields=all_field_values,
        )

        # Update field with scores
        db.update_card_field(field.id, {
            "confidence_score": score.final_score,
            "ocr_score": score.ocr_score,
            "extraction_score": score.extraction_score,
            "validation_score": score.validation_score,
            "cross_ref_score": score.cross_ref_score,
            "needs_review": score.needs_review,
        })

        field_scores.append(score)

    # Document-level score
    doc_scorer = DocumentScorer()
    doc_result = doc_scorer.score_document(field_scores)

    db.update_card(card_id, {
        "card_score": doc_result["document_score"],
        "total_fields": doc_result["total_fields"],
        "filled_fields": len([f for f in fields if f.current_value]),
        "low_confidence_fields": doc_result["low_confidence_fields"],
        "status": "scored",
    })

    db.update_document(card.document_id, {
        "document_score": doc_result["document_score"],
        "status": "completed",
    })

    ws_publish(card.document_id, {
        "step": "complete",
        "card_id": card_id,
        "document_score": doc_result["document_score"],
    })
```

---

## Pipeline Timing Summary

| Step                    | Duration                 | Sync/Async   | Cache?                   |
| ----------------------- | ------------------------ | ------------ | ------------------------ |
| 1. Upload & validate    | 100-500ms                | **Sync**     | Deduplicate by file hash |
| 2. Convert PDF → images | 2-30s                    | Async        | —                        |
| 3. OCR                  | 2-50s (depends on pages) | Async        | Page hash → Redis        |
| 4. Chunking             | 0.5-2s                   | Async        | —                        |
| 5. Embedding            | 1-5s                     | Async        | Stored permanently       |
| 6. Classify + Fill      | 2-5s                     | Async        | Template cache           |
| 7. Scoring              | 0.2-1s                   | Async        | —                        |
| **Total**               | **8-90s**                | Mostly async | Multiple layers          |

User sees upload confirmation in <500ms. Pipeline runs in background with real-time WebSocket updates.

---

## Error Recovery

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def step_3_ocr(self, document_id, pages_data):
    try:
        # ... OCR logic ...
    except RateLimitError:
        # Gemini rate limit — wait and retry
        raise self.retry(countdown=60)
    except APIError as e:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (self.request.retries + 1))
        else:
            # Mark document as failed
            db.update_document(document_id, status="failed", error=str(e))
            ws_publish(document_id, {"step": "ocr", "status": "failed", "error": str(e)})
```
