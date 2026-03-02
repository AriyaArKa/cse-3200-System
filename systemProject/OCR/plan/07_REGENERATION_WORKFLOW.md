# 07 — Regeneration Workflow Design

## Regeneration Levels

| Level         | What                                                    | When                                  | Cost             |
| ------------- | ------------------------------------------------------- | ------------------------------------- | ---------------- |
| **Field**     | Single value (e.g., "Issue Date")                       | User clicks "Regenerate" on one field | Low (~$0.002)    |
| **Section**   | Group of related fields (e.g., "Eligibility Checklist") | Section looks wrong                   | Medium (~$0.005) |
| **Full Card** | Entire template card                                    | Major extraction failure              | High (~$0.015)   |

---

## Architecture

```
User clicks "Regenerate Field"
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. Identify Regeneration Scope             │
│    - Which field(s)?                       │
│    - Which card?                           │
│    - Which document?                       │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│ 2. Fetch Minimal Context                   │
│    - Query vector DB for field-relevant   │
│      chunks (top 3-5)                     │
│    - Include user edits context           │
│    - DO NOT reprocess full document       │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│ 3. Generate New Value                      │
│    - Small prompt + focused context       │
│    - Use model router (cheapest capable)  │
│    - Include previous value as reference  │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│ 4. Score & Validate                        │
│    - Recalculate field confidence          │
│    - Validate format                       │
│    - Compare with previous value           │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│ 5. Store & Version                         │
│    - Save new value                        │
│    - Keep old value in version history    │
│    - Log regeneration event               │
│    - Update vector DB if needed            │
│    - Recalculate document score            │
└───────────────────────────────────────────┘
```

---

## Field-Level Regeneration

```python
class RegenerationService:
    """Handle field, section, and card regeneration."""

    def __init__(self, vector_repo, llm_service, scorer, edit_tracker):
        self.vector_repo = vector_repo
        self.llm = llm_service
        self.scorer = scorer
        self.edits = edit_tracker

    async def regenerate_field(
        self,
        card_id: str,
        field_id: str,
        user_hint: str = None  # Optional user guidance
    ) -> dict:
        """Regenerate a single field value."""

        # 1. Get card and field metadata
        card = await self.db.get_card(card_id)
        field_config = self._get_field_config(card.template_id, field_id)

        # 2. Build minimal context from vector DB
        context = await self._build_field_context(
            card.document_id,
            field_id,
            field_config["type"]
        )

        # 3. Build regeneration prompt
        prompt = self._build_regen_prompt(
            field_config=field_config,
            context=context,
            previous_value=card.fields.get(field_id),
            user_hint=user_hint,
            user_edits=await self.edits.get_field_edits(card_id, field_id),
        )

        # 4. Generate with appropriate model
        model = self.llm.select_model("regenerate", field_config.get("complexity", "simple"))
        new_value = await self.llm.generate(model, prompt)

        # 5. Score
        score = self.scorer.score_field(
            field_id=field_id,
            field_type=field_config["type"],
            extracted_value=new_value,
            ocr_method="regenerated",
            source_chunks=context["chunks"],
            all_fields=card.fields,
        )

        # 6. Create version entry
        version = await self.edits.create_version(
            card_id=card_id,
            field_id=field_id,
            old_value=card.fields.get(field_id),
            new_value=new_value,
            source="ai_regeneration",
            model_used=model["model"],
            confidence=score.final_score,
        )

        # 7. Update card
        await self.db.update_card_field(card_id, field_id, new_value)

        return {
            "field_id": field_id,
            "new_value": new_value,
            "confidence": score.final_score,
            "version_id": version.id,
            "previous_value": card.fields.get(field_id),
        }

    async def regenerate_section(self, card_id: str, section_id: str) -> dict:
        """Regenerate all fields in a section."""
        card = await self.db.get_card(card_id)
        section_fields = self._get_section_fields(card.template_id, section_id)

        results = {}
        for field_id in section_fields:
            results[field_id] = await self.regenerate_field(card_id, field_id)

        return {"section_id": section_id, "fields": results}

    async def regenerate_card(self, card_id: str) -> dict:
        """Regenerate entire card — reprocess from chunks."""
        card = await self.db.get_card(card_id)

        # Get ALL chunks for the document
        all_chunks = self.vector_repo.get_all_chunks(card.document_id)

        # Rebuild full context
        full_context = "\n---\n".join(c["content"] for c in all_chunks)

        # Generate all fields in one LLM call (cheaper than per-field)
        template = self._get_template(card.template_id)
        prompt = self._build_full_card_prompt(template, full_context)

        new_card_data = await self.llm.generate(
            "gemini-2.5-flash",  # Full model for card-level regen
            prompt,
            json_schema=template["schema"],
        )

        # Version all old values
        for field_id, new_value in new_card_data.items():
            await self.edits.create_version(
                card_id=card_id,
                field_id=field_id,
                old_value=card.fields.get(field_id),
                new_value=new_value,
                source="card_regeneration",
            )

        # Update card
        await self.db.update_card_all_fields(card_id, new_card_data)

        # Rescore everything
        all_scores = []
        for field_id, value in new_card_data.items():
            score = self.scorer.score_field(field_id, ...)
            all_scores.append(score)

        doc_score = self.scorer.score_document(all_scores)

        return {
            "card_id": card_id,
            "fields": new_card_data,
            "document_score": doc_score,
        }

    async def _build_field_context(
        self, document_id: str, field_id: str, field_type: str
    ) -> dict:
        """Build minimal context for a single field regeneration."""

        # Convert field name to search query
        query_map = {
            "notice_title": "title subject বিষয় শিরোনাম",
            "issue_date": "date তারিখ dated",
            "department": "department বিভাগ office অফিস",
            "memo_number": "memo স্মারক reference সূত্র number",
            "deadline": "deadline last date শেষ তারিখ",
            "salary": "salary বেতন pay scale",
            "qualification": "qualification যোগ্যতা education শিক্ষা degree",
        }

        query = query_map.get(field_id, field_id.replace("_", " "))
        query_embedding = self.embedding_service.embed_query(query)

        chunks = self.vector_repo.query_for_field(
            query_embedding=query_embedding,
            document_id=document_id,
            field_type=field_type,
            top_k=3,
        )

        return {
            "chunks": chunks,
            "text": "\n".join(c["content"] for c in chunks),
        }

    def _build_regen_prompt(self, field_config, context, previous_value, user_hint, user_edits):
        """Build a focused, cost-efficient regeneration prompt."""

        prompt = f"""Extract the "{field_config['title']}" from this document context.
Type: {field_config['type']}

Context:
{context['text']}
"""

        if previous_value:
            prompt += f"\nPrevious value (may be incorrect): {previous_value}"

        if user_hint:
            prompt += f"\nUser guidance: {user_hint}"

        if user_edits:
            prompt += f"\nUser previously edited this field {len(user_edits)} time(s)."

        prompt += "\n\nReturn only the extracted value, nothing else."

        return prompt
```

---

## Version History & Diff Tracking

```python
class EditTracker:
    """Track all changes to card fields — AI and human."""

    async def create_version(
        self, card_id, field_id, old_value, new_value, source, **kwargs
    ):
        """Record a field change."""
        version = FieldVersion(
            id=uuid.uuid4().hex,
            card_id=card_id,
            field_id=field_id,
            old_value=old_value,
            new_value=new_value,
            source=source,        # "ai_extraction", "ai_regeneration", "user_edit"
            model_used=kwargs.get("model_used"),
            confidence=kwargs.get("confidence"),
            created_at=datetime.utcnow(),
            user_id=kwargs.get("user_id"),
        )

        await self.db.save_version(version)
        return version

    async def get_field_history(self, card_id: str, field_id: str) -> list:
        """Get full version history for a field."""
        versions = await self.db.get_versions(card_id, field_id)

        return [{
            "version_id": v.id,
            "value": v.new_value,
            "source": v.source,          # Who changed it?
            "confidence": v.confidence,
            "timestamp": v.created_at.isoformat(),
            "diff": self._compute_diff(v.old_value, v.new_value),
        } for v in versions]

    def _compute_diff(self, old: str, new: str) -> dict:
        """Compute what changed between versions."""
        from difflib import unified_diff

        if old is None:
            return {"type": "initial", "added": new}

        diff_lines = list(unified_diff(
            (old or "").splitlines(),
            (new or "").splitlines(),
            lineterm=""
        ))

        return {
            "type": "modification",
            "added": [l[1:] for l in diff_lines if l.startswith("+") and not l.startswith("+++")],
            "removed": [l[1:] for l in diff_lines if l.startswith("-") and not l.startswith("---")],
            "similarity": SequenceMatcher(None, old or "", new or "").ratio(),
        }

    async def is_user_edited(self, card_id: str, field_id: str) -> bool:
        """Check if user has manually edited this field."""
        versions = await self.db.get_versions(card_id, field_id)
        return any(v.source == "user_edit" for v in versions)
```

---

## Frontend Regeneration UX

```
┌─────────────────────────────────────────────────┐
│ Issue Date                              ⚠️ 65%  │
│ ┌─────────────────────────────────────────────┐ │
│ │ 12/03/2026                                  │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [✏️ Edit]  [🔄 Regenerate]  [📜 History (3)]     │
│                                                 │
│ ── Version History ──                           │
│ v3 (current) AI regeneration  65%  2min ago     │
│ v2           User edit              5min ago    │
│ v1 (initial) AI extraction    72%  10min ago    │
│                                                 │
│ 💡 AI used 3 source chunks from page 1          │
│    Chunk confidence: 0.85, 0.79, 0.91           │
└─────────────────────────────────────────────────┘
```
