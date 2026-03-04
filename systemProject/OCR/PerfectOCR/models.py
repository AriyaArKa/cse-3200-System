"""
Data models for PerfectOCR System.
Defines structured output matching the master prompt's JSON schema.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import json


# ── Content Block ───────────────────────────────────────
@dataclass
class ContentBlock:
    """A single content block extracted from a page."""

    block_id: int = 0
    type: str = "paragraph"  # header|paragraph|table|form|list|box|footer|divider|image
    position: str = "middle"  # top|middle|bottom|left-column|right-column|full-width
    language: str = "mixed"  # bn|en|mixed
    confidence: str = "high"  # high|medium|low
    text: str = ""
    is_handwritten: bool = False
    _source: str = ""  # which model produced this block

    # Table data (only for type="table")
    table: Optional[Dict[str, Any]] = None

    # Form fields (only for type="form")
    fields: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "block_id": self.block_id,
            "type": self.type,
            "position": self.position,
            "language": self.language,
            "confidence": self.confidence,
            "text": self.text,
            "is_handwritten": self.is_handwritten,
        }
        if self._source:
            d["_source"] = self._source
        if self.table is not None:
            d["table"] = self.table
        if self.fields is not None:
            d["fields"] = self.fields
        return d


# ── Page Result ─────────────────────────────────────────
@dataclass
class PageResult:
    """Structured extraction result for a single page."""

    page_number: int = 1
    content_blocks: List[ContentBlock] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    full_text_reading_order: str = ""
    extraction_notes: List[str] = field(default_factory=list)

    # Metadata
    processing_time_ms: float = 0.0
    models_used: List[str] = field(default_factory=list)
    image_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "content_blocks": [
                b.to_dict() if isinstance(b, ContentBlock) else b
                for b in self.content_blocks
            ],
            "tables": self.tables,
            "forms": self.forms,
            "full_text_reading_order": self.full_text_reading_order,
            "extraction_notes": self.extraction_notes,
        }


# ── Document Metadata ──────────────────────────────────
@dataclass
class DocumentMetadata:
    """Metadata about the document."""

    source: str = ""
    total_pages: int = 0
    language_detected: List[str] = field(default_factory=lambda: ["bn", "en"])
    has_handwriting: bool = False
    has_tables: bool = False
    has_images: bool = False
    has_forms: bool = False
    models_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Document Result ─────────────────────────────────────
@dataclass
class DocumentResult:
    """Complete result for the entire document."""

    document: DocumentMetadata = field(default_factory=DocumentMetadata)
    pages: List[PageResult] = field(default_factory=list)
    extraction_notes: List[str] = field(default_factory=list)

    # Pipeline metadata
    processing_time_ms: float = 0.0
    strategy_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document": self.document.to_dict(),
            "pages": [p.to_dict() for p in self.pages],
            "extraction_notes": self.extraction_notes,
            "_pipeline_metadata": {
                "processing_time_ms": self.processing_time_ms,
                "strategy_used": self.strategy_used,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def detect_document_features(self):
        """Auto-detect document features from page results."""
        for page in self.pages:
            for block in page.content_blocks:
                if isinstance(block, ContentBlock):
                    if block.is_handwritten:
                        self.document.has_handwriting = True
                    if block.type == "table" or block.table:
                        self.document.has_tables = True
                    if block.type == "form" or block.fields:
                        self.document.has_forms = True
                    if block.type == "image":
                        self.document.has_images = True
            if page.tables:
                self.document.has_tables = True
            if page.forms:
                self.document.has_forms = True
