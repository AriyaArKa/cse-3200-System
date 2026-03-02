"""
Pydantic models for request/response validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


# ──────────────────────────── Page‑level models ────────────────────────────


class TableData(BaseModel):
    """A single table extracted from a page."""

    headers: list[str] = Field(default_factory=list, description="Column headers")
    rows: list[list[str]] = Field(default_factory=list, description="Row data")


class LineItem(BaseModel):
    """A single line item (common in invoices)."""

    description: str = ""
    quantity: str = ""
    unit_price: str = ""
    total: str = ""


class PageResult(BaseModel):
    """Structured OCR result for one page."""

    page_number: int
    raw_text: str = ""
    tables: list[TableData] = Field(default_factory=list)
    key_value_pairs: dict[str, str] = Field(default_factory=dict)
    line_items: list[LineItem] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


# ──────────────────────────── Document‑level models ────────────────────────


class DocumentResult(BaseModel):
    """Top‑level result returned by the API."""

    document_type: str = "unknown"
    total_pages: int = 0
    pages: list[PageResult] = Field(default_factory=list)


# ──────────────────────── Validation report (optional) ─────────────────────


class ValidationFlag(BaseModel):
    """Warning emitted during post‑processing validation."""

    page_number: int
    issue: str
    details: str = ""


class ProcessingResponse(BaseModel):
    """Full API response envelope."""

    success: bool = True
    data: DocumentResult | None = None
    validation_flags: list[ValidationFlag] = Field(default_factory=list)
    error: str | None = None
