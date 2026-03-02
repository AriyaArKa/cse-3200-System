"""
Post-processing: assemble raw Gemini results into validated Pydantic models.

Responsibilities:
- Map raw dicts → Pydantic PageResult / DocumentResult
- Detect overall document type via majority vote
- Normalise dates, fix OCR digit errors
- Validate invoice totals
- Flag low-confidence pages
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.schemas import (
    DocumentResult,
    LineItem,
    PageResult,
    TableData,
    ValidationFlag,
)
from app.utils import (
    fix_ocr_number,
    logger,
    normalise_dates_in_dict,
)


# ──────────────────────── Build Pydantic models ──────────────────────────


def _build_page(raw: dict[str, Any]) -> PageResult:
    """Convert a raw dict (from Gemini) into a validated PageResult."""

    # --- tables ---
    tables: list[TableData] = []
    for t in raw.get("tables", []):
        tables.append(
            TableData(
                headers=t.get("headers", []),
                rows=t.get("rows", []),
            )
        )

    # --- key-value pairs (normalise dates) ---
    kvp: dict[str, str] = raw.get("key_value_pairs", {})
    kvp = normalise_dates_in_dict(kvp)

    # --- line items (fix OCR digit errors in numeric fields) ---
    line_items: list[LineItem] = []
    for li in raw.get("line_items", []):
        line_items.append(
            LineItem(
                description=li.get("description", ""),
                quantity=fix_ocr_number(str(li.get("quantity", ""))),
                unit_price=fix_ocr_number(str(li.get("unit_price", ""))),
                total=fix_ocr_number(str(li.get("total", ""))),
            )
        )

    confidence = raw.get("confidence_score", 0.0)
    try:
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    return PageResult(
        page_number=raw.get("page_number", 0),
        raw_text=raw.get("raw_text", ""),
        tables=tables,
        key_value_pairs=kvp,
        line_items=line_items,
        confidence_score=confidence,
    )


# ──────────────────── Document-type majority vote ────────────────────────


def _detect_document_type(raw_pages: list[dict[str, Any]]) -> str:
    """Pick the most common detected_document_type across pages."""
    types = [
        p.get("detected_document_type", "unknown")
        for p in raw_pages
        if p.get("detected_document_type", "unknown") != "unknown"
    ]
    if not types:
        return "unknown"
    counter = Counter(types)
    return counter.most_common(1)[0][0]


# ──────────────────── Invoice total validation ───────────────────────────


def _parse_money(s: str) -> float | None:
    """Try to parse a string as a monetary value."""
    s = s.strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    try:
        return float(s)
    except ValueError:
        return None


def _validate_invoice_totals(
    page: PageResult, page_number: int
) -> list[ValidationFlag]:
    """Check whether the sum of line_item totals ≈ any 'total' key-value."""
    flags: list[ValidationFlag] = []

    if not page.line_items:
        return flags

    item_sum = 0.0
    for li in page.line_items:
        val = _parse_money(li.total)
        if val is not None:
            item_sum += val

    # Look for a "total" or "grand_total" in key-value pairs
    for key in (
        "total",
        "grand_total",
        "amount_due",
        "total_amount",
        "Total",
        "Grand Total",
    ):
        if key in page.key_value_pairs:
            doc_total = _parse_money(page.key_value_pairs[key])
            if doc_total is not None and abs(doc_total - item_sum) > 0.02:
                flags.append(
                    ValidationFlag(
                        page_number=page_number,
                        issue="line_item_total_mismatch",
                        details=(
                            f"Sum of line items = {item_sum:.2f}, "
                            f"but document total ({key}) = {doc_total:.2f}"
                        ),
                    )
                )
            break

    return flags


# ──────────────────── Low-confidence detection ───────────────────────────


def _flag_low_confidence(
    page: PageResult, threshold: float = 0.85
) -> list[ValidationFlag]:
    if page.confidence_score < threshold:
        return [
            ValidationFlag(
                page_number=page.page_number,
                issue="low_confidence",
                details=f"Confidence {page.confidence_score:.2f} < {threshold}",
            )
        ]
    return []


# ──────────────── Multi-page invoice merge (simple) ──────────────────────


def _merge_multipage_line_items(pages: list[PageResult]) -> list[PageResult]:
    """
    If multiple pages carry line_items (same invoice), we keep them on their
    respective pages but also add a combined key-value entry on page 1.
    """
    all_items: list[LineItem] = []
    for p in pages:
        all_items.extend(p.line_items)

    if len(all_items) > 0 and pages:
        total = sum(_parse_money(li.total) or 0.0 for li in all_items)
        pages[0].key_value_pairs["computed_line_items_total"] = f"{total:.2f}"

    return pages


# ═══════════════════════════ Public entry point ══════════════════════════


def build_document_result(
    raw_pages: list[dict[str, Any]],
) -> tuple[DocumentResult, list[ValidationFlag]]:
    """
    Convert raw Gemini results into a fully validated DocumentResult
    and a list of ValidationFlags.
    """
    doc_type = _detect_document_type(raw_pages)

    pages = [_build_page(rp) for rp in raw_pages]
    pages = _merge_multipage_line_items(pages)

    flags: list[ValidationFlag] = []
    for page in pages:
        flags.extend(_flag_low_confidence(page))
        if doc_type in ("invoice", "receipt"):
            flags.extend(_validate_invoice_totals(page, page.page_number))

    result = DocumentResult(
        document_type=doc_type,
        total_pages=len(pages),
        pages=pages,
    )

    if flags:
        logger.warning("Validation flags: %s", [f.issue for f in flags])

    return result, flags
