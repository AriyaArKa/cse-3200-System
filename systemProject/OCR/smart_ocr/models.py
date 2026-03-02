"""
Data models for Smart OCR System.
Defines structured output for blocks, pages, and documents.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class LanguageType(str, Enum):
    BANGLA_HEAVY = "bangla_heavy"
    ENGLISH_HEAVY = "english_heavy"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    HYBRID = "hybrid"


class RoutingDecision(str, Enum):
    ACCEPT = "accept"  # High confidence → accept as-is
    LOCAL_CORRECTION = "local_correction"  # Medium → correction layer
    GEMINI_FALLBACK = "gemini_fallback"  # Low → send to Gemini


@dataclass
class Block:
    """A logical text block (paragraph or layout segment)."""

    block_id: str = ""
    detected_language_type: str = LanguageType.UNKNOWN.value
    bangla_ratio: float = 0.0
    english_ratio: float = 0.0
    raw_text: str = ""
    corrected_text: str = ""
    confidence_score: float = 0.0
    routing_decision: str = RoutingDecision.ACCEPT.value
    gemini_used: bool = False
    ocr_word_confidences: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PageResult:
    """Result for a single PDF page."""

    page_id: int = 0
    source_type: str = SourceType.NATIVE_TEXT.value
    blocks: List[Block] = field(default_factory=list)
    page_confidence_score: float = 0.0
    page_language_distribution: Dict[str, float] = field(default_factory=dict)
    image_path: Optional[str] = None
    native_text_available: bool = False
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["blocks"] = [b.to_dict() if isinstance(b, Block) else b for b in self.blocks]
        return d

    def get_full_text(self) -> str:
        """Get the best available text for this page (corrected > raw)."""
        texts = []
        for block in self.blocks:
            text = block.corrected_text if block.corrected_text else block.raw_text
            if text.strip():
                texts.append(text.strip())
        return "\n\n".join(texts)


@dataclass
class DocumentResult:
    """Result for the entire document."""

    document_name: str = ""
    total_pages: int = 0
    pages: List[PageResult] = field(default_factory=list)
    overall_confidence: float = 0.0
    gemini_usage_summary: Dict[str, Any] = field(default_factory=dict)
    language_distribution_summary: Dict[str, float] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pages"] = [
            p.to_dict() if isinstance(p, PageResult) else p for p in self.pages
        ]
        return d

    def to_old_format(self) -> Dict[str, Any]:
        """
        Convert to the old output format for backward compatibility.
        Old format: {"pages": [{"source_file": "...", "data": {...}}]}
        """
        old_pages = []
        for page in self.pages:
            # Build structured data from blocks
            page_data = {}
            full_text = page.get_full_text()

            # If blocks contain structured content, use it
            if len(page.blocks) == 1 and page.blocks[0].corrected_text:
                # Try to parse as JSON (if Gemini returned structured JSON)
                try:
                    page_data = json.loads(page.blocks[0].corrected_text)
                except (json.JSONDecodeError, TypeError):
                    page_data = {"text": page.blocks[0].corrected_text}
            elif page.blocks:
                # Multiple blocks → assemble
                block_texts = []
                for b in page.blocks:
                    text = b.corrected_text if b.corrected_text else b.raw_text
                    if text.strip():
                        block_texts.append(text.strip())
                page_data = {
                    "text_blocks": block_texts,
                    "full_text": "\n\n".join(block_texts),
                }
            else:
                page_data = {"text": full_text}

            # Add metadata
            page_data["_metadata"] = {
                "source_type": page.source_type,
                "confidence": page.page_confidence_score,
                "language_distribution": page.page_language_distribution,
                "gemini_blocks": sum(1 for b in page.blocks if b.gemini_used),
                "total_blocks": len(page.blocks),
            }

            source_file = f"page_{page.page_id}.json"
            old_pages.append(
                {
                    "source_file": source_file,
                    "data": page_data,
                }
            )

        return {
            "pages": old_pages,
            "_document_metadata": {
                "overall_confidence": self.overall_confidence,
                "gemini_usage_summary": self.gemini_usage_summary,
                "language_distribution_summary": self.language_distribution_summary,
                "processing_time_ms": self.processing_time_ms,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_old_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_old_format(), ensure_ascii=False, indent=indent)
