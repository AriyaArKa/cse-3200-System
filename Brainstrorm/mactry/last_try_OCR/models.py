"""
Data models for the OCR pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def to_list(self) -> list:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass
class ContentBlock:
    block_id: int
    type: str  # header, paragraph, list, footer, box, divider, signature, unknown
    language: str  # bn, en, mixed
    text: str
    confidence: float
    bbox: Optional[BBox] = None
    is_handwritten: bool = False

    def to_dict(self) -> dict:
        d = {
            "block_id": self.block_id,
            "type": self.type,
            "language": self.language,
            "text": self.text,
            "confidence": round(self.confidence, 4),
        }
        if self.bbox:
            d["bbox"] = self.bbox.to_list()
        if self.is_handwritten:
            d["is_handwritten"] = True
        return d


@dataclass
class TableResult:
    table_id: int
    structure_confidence: float
    rows: List[List[str]]

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "structure_confidence": round(self.structure_confidence, 4),
            "rows": self.rows,
        }


@dataclass
class ImageResult:
    image_id: int
    type: str  # chart, photo, diagram, unknown
    detected_text: str
    description: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "type": self.type,
            "detected_text": self.detected_text,
            "description": self.description,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class PageExtraction:
    method: str  # digital, ocr_local, ocr_api
    engine: str
    confidence_score: float
    correction_applied: bool = False
    numeric_validation_passed: bool = True

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "engine": self.engine,
            "confidence_score": round(self.confidence_score, 4),
            "correction_applied": self.correction_applied,
            "numeric_validation_passed": self.numeric_validation_passed,
        }


@dataclass
class PageResult:
    page_number: int
    extraction: PageExtraction
    content_blocks: List[ContentBlock] = field(default_factory=list)
    tables: List[TableResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    full_text: str = ""
    source_image_path: str = ""
    verified: bool = False
    domain: str = "unknown"
    confidence_tier: str = ""
    log: dict = field(default_factory=dict)
    decisions: List[dict] = field(default_factory=list)

    def to_corpus_record(self) -> dict:
        """Convert page result into a flat corpus row for parquet/jsonl storage."""
        bn_chars = sum(1 for ch in self.full_text if 0x0980 <= ord(ch) <= 0x09FF)
        total_chars = max(len(self.full_text), 1)
        language_ratio_bn = bn_chars / total_chars
        word_count = len([w for w in self.full_text.split() if w.strip()])
        char_count = len(self.full_text)

        tier = self.confidence_tier.strip().lower() if self.confidence_tier else ""
        if not tier:
            if self.extraction.confidence_score >= 0.85 and self.verified:
                tier = "gold"
            elif self.extraction.confidence_score >= 0.65:
                tier = "silver"
            else:
                tier = "bronze"

        return {
            "page_number": self.page_number,
            "full_text": self.full_text,
            "source_image_path": self.source_image_path,
            "engine": self.extraction.engine,
            "confidence_score": round(self.extraction.confidence_score, 4),
            "verified": self.verified,
            "domain": self.domain or "unknown",
            "confidence_tier": tier,
            "language_ratio_bn": round(language_ratio_bn, 4),
            "has_table": bool(self.tables),
            "has_image": bool(self.images),
            "word_count": word_count,
            "char_count": char_count,
        }

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "extraction": self.extraction.to_dict(),
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "tables": [t.to_dict() for t in self.tables],
            "images": [i.to_dict() for i in self.images],
            "full_text": self.full_text,
            "source_image_path": self.source_image_path,
            "verified": self.verified,
            "domain": self.domain,
            "confidence_tier": self.to_corpus_record()["confidence_tier"],
            "decisions": self.decisions,
        }


@dataclass
class DocumentResult:
    source: str
    total_pages: int
    language_detected: List[str] = field(default_factory=list)
    has_handwriting: bool = False
    has_tables: bool = False
    has_images: bool = False
    pages_processed_locally: int = 0
    pages_sent_to_api: int = 0
    overall_confidence: float = 0.0
    pages: List[PageResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    document_decisions: List[dict] = field(default_factory=list)

    def _decision_summary(self) -> dict:
        by_sev: dict = {"info": 0, "warning": 0, "error": 0}
        keywords: set = set()
        for d in self.document_decisions:
            sev = d.get("severity", "info")
            by_sev[sev] = by_sev.get(sev, 0) + 1
            keywords.add(d["keyword"])
        return {
            "total": len(self.document_decisions),
            "by_severity": by_sev,
            "unique_keywords": sorted(keywords),
        }

    def to_dict(self) -> dict:
        return {
            "document": {
                "source": self.source,
                "total_pages": self.total_pages,
                "language_detected": self.language_detected,
                "has_handwriting": self.has_handwriting,
                "has_tables": self.has_tables,
                "has_images": self.has_images,
                "processing_summary": {
                    "pages_processed_locally": self.pages_processed_locally,
                    "pages_sent_to_api": self.pages_sent_to_api,
                    "overall_confidence": round(self.overall_confidence, 4),
                    "processing_time_ms": round(self.processing_time_ms, 2),
                },
                "decision_summary": self._decision_summary(),
                "all_decisions": self.document_decisions,
            },
            "pages": [p.to_dict() for p in self.pages],
        }
