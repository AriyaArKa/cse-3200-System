# 05 — Confidence Scoring System

## Scoring Architecture

Every extracted value gets a confidence score at two levels:

1. **Field-level** — how confident are we about each individual value?
2. **Document-level** — overall extraction quality for the whole document?

---

## Field-Level Confidence Score

### Formula

```
field_score = (w1 × ocr_confidence)
            + (w2 × extraction_confidence)
            + (w3 × format_validation_score)
            + (w4 × cross_reference_score)
```

Default weights:

```python
WEIGHTS = {
    "ocr_confidence": 0.25,       # How clear was the source text?
    "extraction_confidence": 0.35, # How certain is the LLM about extraction?
    "format_validation": 0.25,     # Does it match expected format?
    "cross_reference": 0.15,       # Verified against other fields?
}
```

### Implementation

```python
from dataclasses import dataclass
from typing import Optional
import re
from datetime import datetime


@dataclass
class FieldScore:
    field_id: str
    value: str
    ocr_score: float          # 0.0 - 1.0
    extraction_score: float   # 0.0 - 1.0
    validation_score: float   # 0.0 - 1.0
    cross_ref_score: float    # 0.0 - 1.0
    final_score: float        # Weighted composite
    method: str               # "ocr", "native", "cached", "user_edited"
    needs_review: bool        # True if final_score < 0.7


class ConfidenceScorer:
    """Calculate confidence scores for extracted fields."""

    REVIEW_THRESHOLD = 0.7    # Below this → flag for human review
    HIGH_CONFIDENCE = 0.9     # Above this → auto-accept

    def score_field(
        self,
        field_id: str,
        field_type: str,        # "date", "text", "number", "list", etc.
        extracted_value: str,
        ocr_method: str,        # "native", "gemini", "cached"
        source_chunks: list[dict],
        all_fields: dict,       # Other fields for cross-reference
    ) -> FieldScore:
        """Calculate composite confidence for a single field."""

        # 1. OCR Confidence
        ocr_score = self._ocr_confidence(ocr_method, source_chunks)

        # 2. Extraction Confidence (LLM certainty)
        extraction_score = self._extraction_confidence(
            extracted_value, source_chunks
        )

        # 3. Format Validation
        validation_score = self._format_validation(field_type, extracted_value)

        # 4. Cross-Reference
        cross_ref_score = self._cross_reference(
            field_id, extracted_value, all_fields
        )

        # Weighted composite
        final = (
            WEIGHTS["ocr_confidence"] * ocr_score +
            WEIGHTS["extraction_confidence"] * extraction_score +
            WEIGHTS["format_validation"] * validation_score +
            WEIGHTS["cross_reference"] * cross_ref_score
        )

        return FieldScore(
            field_id=field_id,
            value=extracted_value,
            ocr_score=ocr_score,
            extraction_score=extraction_score,
            validation_score=validation_score,
            cross_ref_score=cross_ref_score,
            final_score=round(final, 3),
            method=ocr_method,
            needs_review=final < self.REVIEW_THRESHOLD,
        )

    # ---- Component Scorers ----

    def _ocr_confidence(self, method: str, chunks: list[dict]) -> float:
        """Score based on how the text was obtained."""
        base_scores = {
            "native": 0.95,     # Direct PDF text extraction = very reliable
            "cached": 0.90,     # Previously verified OCR
            "gemini": 0.85,     # Gemini OCR = good but not perfect
            "user_edited": 1.0, # User manually verified
        }
        base = base_scores.get(method, 0.5)

        # Adjust based on chunk quality
        if chunks:
            avg_chunk_confidence = sum(
                c.get("ocr_confidence", 0.8) for c in chunks
            ) / len(chunks)
            return (base + avg_chunk_confidence) / 2

        return base

    def _extraction_confidence(self, value: str, chunks: list[dict]) -> float:
        """Score based on how well the extracted value matches source text."""
        if not value or not chunks:
            return 0.0

        # Check if value appears verbatim in any source chunk
        source_text = " ".join(c.get("content", "") for c in chunks)

        if value in source_text:
            return 1.0  # Exact match — very confident

        # Fuzzy match
        from difflib import SequenceMatcher
        best_ratio = 0.0
        for chunk in chunks:
            ratio = SequenceMatcher(None, value, chunk.get("content", "")).ratio()
            best_ratio = max(best_ratio, ratio)

        return min(best_ratio + 0.2, 1.0)  # Boost slightly for partial matches

    def _format_validation(self, field_type: str, value: str) -> float:
        """Validate extracted value matches expected format."""

        validators = {
            "date": self._validate_date,
            "date_list": self._validate_date_list,
            "number": self._validate_number,
            "email": self._validate_email,
            "phone": self._validate_phone,
            "text": lambda v: 1.0 if len(v.strip()) > 0 else 0.0,
            "list": lambda v: 1.0 if v else 0.5,
            "table": lambda v: 1.0 if v else 0.3,
        }

        validator = validators.get(field_type, lambda v: 0.8)
        return validator(value)

    def _validate_date(self, value: str) -> float:
        """Check if value looks like a valid date."""
        date_patterns = [
            r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',     # DD/MM/YYYY
            r'\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}',         # YYYY-MM-DD
            r'[\u09E6-\u09EF]{1,2}[/\-\.][\u09E6-\u09EF]{1,2}',  # Bangla numerals
        ]
        for pattern in date_patterns:
            if re.search(pattern, value):
                return 1.0

        # Try parsing
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]:
            try:
                datetime.strptime(value.strip(), fmt)
                return 1.0
            except ValueError:
                continue

        return 0.3  # Has some text but not a recognizable date

    def _validate_date_list(self, value: str) -> float:
        if isinstance(value, list):
            scores = [self._validate_date(str(v)) for v in value]
            return sum(scores) / len(scores) if scores else 0.0
        return self._validate_date(str(value))

    def _validate_number(self, value: str) -> float:
        try:
            float(str(value).replace(",", "").replace("৳", "").strip())
            return 1.0
        except ValueError:
            return 0.2

    def _validate_email(self, value: str) -> float:
        return 1.0 if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value) else 0.1

    def _validate_phone(self, value: str) -> float:
        digits = re.sub(r'\D', '', value)
        return 1.0 if 10 <= len(digits) <= 15 else 0.2

    def _cross_reference(self, field_id: str, value: str, all_fields: dict) -> float:
        """Cross-validate against other extracted fields."""

        # Example: if "issue_date" exists and "effective_date" exists,
        # effective_date should be >= issue_date
        if field_id == "effective_date" and "issue_date" in all_fields:
            try:
                issue = self._parse_date(all_fields["issue_date"])
                effective = self._parse_date(value)
                if effective >= issue:
                    return 1.0
                else:
                    return 0.3  # Effective before issue = suspicious
            except:
                return 0.5  # Can't compare

        # Default: no cross-reference applicable
        return 0.8

    def _parse_date(self, value: str):
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {value}")
```

---

## Document-Level Confidence Score

```python
class DocumentScorer:
    """Calculate overall document extraction quality."""

    def score_document(self, field_scores: list[FieldScore]) -> dict:
        """Aggregate field scores into document-level score."""

        if not field_scores:
            return {"score": 0.0, "status": "empty"}

        scores = [f.final_score for f in field_scores]

        # Weighted average (critical fields weigh more)
        critical_fields = {"notice_title", "issue_date", "memo_number",
                          "account_holder_name", "position_title"}

        weighted_sum = 0
        weight_total = 0

        for fs in field_scores:
            weight = 2.0 if fs.field_id in critical_fields else 1.0
            weighted_sum += fs.final_score * weight
            weight_total += weight

        doc_score = weighted_sum / weight_total if weight_total else 0.0

        # Count issues
        low_confidence_count = sum(1 for f in field_scores if f.needs_review)

        return {
            "document_score": round(doc_score, 3),
            "total_fields": len(field_scores),
            "low_confidence_fields": low_confidence_count,
            "high_confidence_fields": sum(
                1 for f in field_scores if f.final_score >= 0.9
            ),
            "status": self._classify(doc_score, low_confidence_count),
            "needs_review": low_confidence_count > 0,
            "field_scores": {f.field_id: f.final_score for f in field_scores},
        }

    def _classify(self, score: float, low_count: int) -> str:
        if score >= 0.9 and low_count == 0:
            return "excellent"   # Green badge
        elif score >= 0.7:
            return "good"        # Blue badge
        elif score >= 0.5:
            return "needs_review" # Yellow badge
        else:
            return "poor"        # Red badge
```

---

## Recalculation After Regeneration

```python
def on_field_regenerated(self, card_id: str, field_id: str, new_value: str):
    """Recalculate scores after AI regeneration."""

    # 1. Re-score the regenerated field
    new_field_score = self.scorer.score_field(
        field_id=field_id,
        field_type=self._get_field_type(card_id, field_id),
        extracted_value=new_value,
        ocr_method="gemini",  # Regenerated by LLM
        source_chunks=self._get_relevant_chunks(card_id, field_id),
        all_fields=self._get_all_fields(card_id),
    )

    # 2. Update field score in DB
    self.db.update_field_score(card_id, field_id, new_field_score)

    # 3. Recalculate document score
    all_field_scores = self.db.get_all_field_scores(card_id)
    doc_score = self.doc_scorer.score_document(all_field_scores)
    self.db.update_document_score(card_id, doc_score)

    # 4. Notify frontend via WebSocket
    await self.ws_manager.send(card_id, {
        "event": "score_updated",
        "field_id": field_id,
        "new_score": new_field_score.final_score,
        "document_score": doc_score["document_score"],
    })
```

---

## Score Display (Frontend)

```
┌─────────────────────────────────────────┐
│ Student Action Card          Score: 87% │
│ ────────────────────────────────────────│
│                                         │
│ Notice Title:                     ✅ 95%│
│ "ছুটি ঘোষণা ও শিক্ষা কার্যক্রম..."      │
│                                         │
│ Department:                       ✅ 92%│
│ "কম্পিউটার সায়েন্স বিভাগ"               │
│                                         │
│ Issue Date:                       ⚠️ 65%│  ← Needs review
│ "12/03/2026" (format uncertain)         │
│ [Edit] [Regenerate]                     │
│                                         │
│ Important Dates:                  ✅ 88%│
│ • March 15 — Last date                  │
│ • March 20 — Results                    │
│                                         │
│ Risk if Ignored:                  ✅ 90%│
│ "Students may miss deadline..."         │
│ [Regenerate]                            │
└─────────────────────────────────────────┘
```
