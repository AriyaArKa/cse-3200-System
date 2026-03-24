# 02 — OCR Optimization Strategy

## Current Problem

Your current flow: **Every page → image → Gemini API call**  
Cost: ~$0.01-0.03 per page (Gemini 2.5 Flash pricing: ~$0.10/1M input tokens for images)  
A 50-page PDF = 50 API calls = $0.50-1.50 per document  
At 1000 docs/day = **$500-1500/day** — unsustainable.

---

## Hybrid OCR Strategy (Most Important Optimization)

### Decision Tree: When to use what

```
PDF Uploaded
    │
    ▼
┌─────────────────────────┐
│ STEP 1: Try native      │
│ text extraction          │
│ (PyMuPDF/pdfplumber)     │
└───────────┬─────────────┘
            │
            ▼
    ┌───────────────┐
    │ Text found?   │
    │ len > 50 chars│
    │ per page?     │
    └───┬───────┬───┘
        │       │
       YES      NO (scanned PDF / image-based)
        │       │
        ▼       ▼
┌──────────┐  ┌──────────────────────┐
│ Use      │  │ STEP 2: Convert to   │
│ native   │  │ image → Gemini OCR   │
│ text     │  │ (existing pipeline)  │
│ directly │  └──────────────────────┘
│ FREE!    │
└──────────┘
```

### Implementation

```python
import fitz  # PyMuPDF — fast, reliable
import pdfplumber

class HybridOCRService:
    """Try native extraction first. Fall back to Gemini only when needed."""

    NATIVE_TEXT_THRESHOLD = 50  # Min chars to consider page as text-based

    def process_page(self, pdf_path: str, page_num: int) -> dict:
        """Process a single page with optimal cost strategy."""

        # STEP 1: Try native text extraction (FREE)
        native_text = self._extract_native_text(pdf_path, page_num)

        if len(native_text.strip()) > self.NATIVE_TEXT_THRESHOLD:
            return {
                "text": native_text,
                "method": "native",
                "cost": 0.0,
                "confidence": 0.95,  # Native extraction is very reliable
            }

        # STEP 2: Check if we have cached OCR for this page
        page_hash = self._compute_page_hash(pdf_path, page_num)
        cached = self.cache.get(f"ocr:{page_hash}")
        if cached:
            return {
                "text": cached,
                "method": "cached_gemini",
                "cost": 0.0,
                "confidence": 0.90,
            }

        # STEP 3: Fall back to Gemini OCR (COSTS MONEY)
        image_path = self._convert_page_to_image(pdf_path, page_num)
        ocr_text = self._gemini_ocr(image_path)

        # Cache the result
        self.cache.set(f"ocr:{page_hash}", ocr_text, ex=86400 * 30)  # 30 days

        return {
            "text": ocr_text,
            "method": "gemini",
            "cost": 0.015,  # estimated per-page cost
            "confidence": 0.85,
        }

    def _extract_native_text(self, pdf_path: str, page_num: int) -> str:
        """Extract text using PyMuPDF (free, fast)."""
        doc = fitz.open(pdf_path)
        page = doc[page_num]

        # Get text with layout preservation
        text = page.get_text("text")

        # Also try extracting tables with pdfplumber for structured data
        with pdfplumber.open(pdf_path) as pdf:
            plumber_page = pdf.pages[page_num]
            tables = plumber_page.extract_tables()

        doc.close()

        return text + "\n" + self._format_tables(tables)

    def _compute_page_hash(self, pdf_path: str, page_num: int) -> str:
        """Hash page content for deduplication."""
        import hashlib
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        # Hash the raw page bytes (catches identical pages across uploads)
        page_bytes = page.get_pixmap(dpi=72).tobytes()
        doc.close()
        return hashlib.sha256(page_bytes).hexdigest()[:16]
```

### Cost Savings Projection

| Scenario                   | Without Hybrid | With Hybrid                         | Savings             |
| -------------------------- | -------------- | ----------------------------------- | ------------------- |
| 100% text PDFs             | $15/1000 docs  | $0                                  | **100%**            |
| 50% text / 50% scanned     | $15/1000 docs  | $7.50                               | **50%**             |
| 100% scanned (worst case)  | $15/1000 docs  | $15 (+ caching saves on re-uploads) | **0-30%** (caching) |
| **Typical real-world mix** | $15/1000 docs  | **$3-5/1000 docs**                  | **65-80%**          |

---

## Layout-Aware Extraction

For PDFs with complex layouts (tables, columns, headers/footers), use structured extraction:

```python
def extract_with_layout(self, pdf_path: str, page_num: int) -> dict:
    """Extract text preserving document structure."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num]

        result = {
            "plain_text": page.extract_text(),
            "tables": [],
            "metadata": {
                "width": page.width,
                "height": page.height,
                "page_number": page_num + 1,
            }
        }

        # Extract tables separately
        tables = page.extract_tables()
        for i, table in enumerate(tables):
            result["tables"].append({
                "table_id": i,
                "headers": table[0] if table else [],
                "rows": table[1:] if len(table) > 1 else [],
            })

        return result
```

---

## Batch Processing Strategy

### Problem

Sending 50 pages one-by-one = 50 sequential API calls = slow + rate limit risk.

### Solution: Controlled Concurrency

```python
import asyncio
from asyncio import Semaphore

class BatchOCRProcessor:
    MAX_CONCURRENT = 5  # Gemini rate limit safe zone

    async def process_document(self, pages: list[str]) -> list[dict]:
        """Process all pages with controlled concurrency."""
        semaphore = Semaphore(self.MAX_CONCURRENT)

        async def process_with_limit(page_path, page_num):
            async with semaphore:
                return await self.ocr_single_page(page_path, page_num)

        tasks = [
            process_with_limit(path, i)
            for i, path in enumerate(pages)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle failures gracefully
        final = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final.append({"page": i, "error": str(result), "retry": True})
            else:
                final.append(result)

        return final
```

---

## Duplicate Page Detection

Many PDFs have repeated headers, footers, or even duplicate pages. Detect and skip:

```python
def detect_duplicates(self, page_hashes: list[str]) -> dict:
    """Find duplicate pages to avoid redundant OCR."""
    seen = {}
    duplicates = {}

    for i, hash_val in enumerate(page_hashes):
        if hash_val in seen:
            duplicates[i] = seen[hash_val]  # page i is duplicate of page seen[hash_val]
        else:
            seen[hash_val] = i

    return duplicates
    # Usage: skip OCR for duplicate pages, copy result from original

# In pipeline:
# hashes = [compute_page_hash(pdf, i) for i in range(total_pages)]
# dupes = detect_duplicates(hashes)
# for page_num in range(total_pages):
#     if page_num in dupes:
#         results[page_num] = results[dupes[page_num]]  # Copy, don't re-OCR
#     else:
#         results[page_num] = await ocr(page_num)
```

---

## OCR Caching Architecture

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│ New Page     │─────▶│ Compute Hash │─────▶│ Check Redis  │
│ (image)      │      │ (SHA-256 of  │      │ Cache        │
│              │      │  pixel data) │      │              │
└─────────────┘      └──────────────┘      └───┬──────┬───┘
                                               │      │
                                          HIT  │      │ MISS
                                               ▼      ▼
                                        ┌────────┐  ┌──────────┐
                                        │ Return │  │ Gemini   │
                                        │ cached │  │ OCR call │
                                        │ result │  │          │
                                        │ $0.00  │  │ $0.015   │
                                        └────────┘  └────┬─────┘
                                                         │
                                                         ▼
                                                  ┌──────────────┐
                                                  │ Store in     │
                                                  │ Redis cache  │
                                                  │ TTL: 30 days │
                                                  └──────────────┘
```

### Cache Key Strategy

```python
# Level 1: Exact page match (pixel-level hash)
cache_key = f"ocr:pixel:{sha256_of_page_pixels[:16]}"

# Level 2: Document-level cache (same PDF re-uploaded)
cache_key = f"ocr:doc:{sha256_of_pdf_bytes[:16]}:page:{page_num}"

# Level 3: Cross-document similar page (fuzzy match)
# → Only for Phase 3, uses perceptual hashing (pHash)
```

---

## Gemini Prompt Optimization (Reduce Tokens = Reduce Cost)

### Current prompt (wasteful — 47 tokens):

```
Extract ALL text exactly as written.
Extract all visible content from this image in STRICT structured JSON format only.
Preserve original Bangla characters exactly.
Do NOT translate.
Return STRICT valid JSON only.
Do NOT include markdown formatting.
Do NOT include explanations.
Ensure UTF-8 correctness.
```

### Optimized prompt (24 tokens — 49% reduction):

```
Extract all text as structured JSON. Preserve Bangla exactly. No markdown, no explanation. UTF-8 only.
```

### With JSON schema enforcement (best — forces structured output):

```python
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[optimized_prompt, image],
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body_text": {"type": "string"},
                "tables": {"type": "array", "items": {"type": "object"}},
                "dates": {"type": "array", "items": {"type": "string"}},
                "signatures": {"type": "array", "items": {"type": "string"}},
            }
        }
    }
)
```

**Why this matters:** JSON schema enforcement eliminates markdown wrapping, reduces output tokens, and guarantees parseable JSON — saving your `clean_json_text()` step entirely.

---

## DPI Optimization

Your current DPI is 300. For many documents, this is overkill:

| DPI | Image Size | OCR Quality            | Use Case                       |
| --- | ---------- | ---------------------- | ------------------------------ |
| 150 | ~0.3 MB    | Good for clean text    | Government notices, typed docs |
| 200 | ~0.5 MB    | Good for mixed content | Most documents                 |
| 300 | ~1.2 MB    | Best quality           | Handwritten, low-quality scans |

```python
def select_dpi(self, pdf_path: str, page_num: int) -> int:
    """Adaptive DPI based on page content."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    # Check if page has embedded images (scanned)
    images = page.get_images()
    native_text = page.get_text("text")

    if len(native_text.strip()) > 100:
        return 150  # Text-based PDF, low DPI fine
    elif len(images) > 0:
        # Check image resolution
        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)
            if base_image["width"] < 1000:
                return 300  # Low-res source, need high DPI
        return 200  # Normal scanned doc
    else:
        return 200  # Default
```

**Savings:** Reducing from 300→200 DPI cuts image size by ~58%, reducing Gemini input token cost proportionally.
