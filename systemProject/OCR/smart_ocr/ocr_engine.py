"""
PaddleOCR Engine Module.
Handles OCR using PaddleOCR for both Bangla and English text.
Returns block-level results with per-word confidence scores.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import PaddleOCR to avoid startup overhead
_paddle_engines: Dict[str, Any] = {}


def _get_paddle_engine(lang: str = "en"):
    """Get or create PaddleOCR engine (lazy initialization, cached)."""
    global _paddle_engines
    if lang not in _paddle_engines:
        try:
            from paddleocr import PaddleOCR
            from . import config

            logger.info(f"Initializing PaddleOCR engine (lang={lang})...")
            engine = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                use_gpu=config.PADDLE_USE_GPU,
                show_log=config.PADDLE_SHOW_LOG,
                enable_mkldnn=True,
            )
            _paddle_engines[lang] = engine
            logger.info(f"PaddleOCR engine ready (lang={lang})")
        except ImportError:
            logger.error(
                "PaddleOCR not installed. Install with: pip install paddleocr paddlepaddle"
            )
            raise
        except Exception as e:
            logger.error(f"PaddleOCR init failed: {e}")
            raise

    return _paddle_engines[lang]


class OCRBlock:
    """A detected text block from PaddleOCR."""

    def __init__(
        self,
        text: str,
        confidence: float,
        bbox: List[List[float]],
        block_index: int = 0,
    ):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        self.block_index = block_index

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox,
            "block_index": self.block_index,
        }


class PaddleOCREngine:
    """
    Wrapper around PaddleOCR for multilingual (Bangla + English) OCR.
    Returns structured block-level results with confidence scores.
    """

    def __init__(self):
        self._en_engine = None
        self._bn_engine = None

    def _ensure_engines(self):
        """Lazy-load engines on first use."""
        if self._en_engine is None:
            self._en_engine = _get_paddle_engine("en")
        # Bangla engine - try to load, fall back to English if unavailable
        if self._bn_engine is None:
            try:
                from . import config

                self._bn_engine = _get_paddle_engine(config.PADDLE_BANGLA_LANG)
            except Exception as e:
                logger.warning(
                    f"Bangla PaddleOCR model not available: {e}. Using English model only."
                )
                self._bn_engine = self._en_engine

    def ocr_image(self, image_path: str, lang_hint: str = "auto") -> List[OCRBlock]:
        """
        Run OCR on an image file.

        Args:
            image_path: Path to the image file
            lang_hint: "bangla", "english", or "auto" (runs both, picks best)

        Returns:
            List of OCRBlock with text, confidence, and bounding boxes
        """
        self._ensure_engines()
        path = str(Path(image_path).resolve())

        if lang_hint == "bangla":
            return self._run_ocr(self._bn_engine, path)
        elif lang_hint == "english":
            return self._run_ocr(self._en_engine, path)
        else:
            # Auto: run both and merge/pick best results
            return self._run_auto_ocr(path)

    def _run_ocr(self, engine, image_path: str) -> List[OCRBlock]:
        """Run OCR with a specific engine."""
        try:
            results = engine.ocr(image_path, cls=True)
            if not results or not results[0]:
                logger.warning(f"No OCR results for {image_path}")
                return []

            blocks = []
            for idx, line in enumerate(results[0]):
                bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = line[1][0]
                confidence = float(line[1][1])
                blocks.append(
                    OCRBlock(
                        text=text,
                        confidence=confidence,
                        bbox=bbox,
                        block_index=idx,
                    )
                )

            logger.info(f"OCR found {len(blocks)} blocks in {Path(image_path).name}")
            return blocks

        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return []

    def _run_auto_ocr(self, image_path: str) -> List[OCRBlock]:
        """
        Run both English and Bangla engines, merge results.
        For each detected region, keep the result with higher confidence.
        """
        en_blocks = self._run_ocr(self._en_engine, image_path)

        # If Bangla engine is different from English, run it too
        if self._bn_engine is not self._en_engine:
            bn_blocks = self._run_ocr(self._bn_engine, image_path)
            return self._merge_results(en_blocks, bn_blocks)

        return en_blocks

    def _merge_results(
        self, en_blocks: List[OCRBlock], bn_blocks: List[OCRBlock]
    ) -> List[OCRBlock]:
        """
        Merge English and Bangla OCR results.
        For overlapping regions, keep the one with higher confidence.
        """
        if not bn_blocks:
            return en_blocks
        if not en_blocks:
            return bn_blocks

        # Simple merge: if same number of blocks, compare pairwise
        # Otherwise use the set with higher average confidence
        if len(en_blocks) == len(bn_blocks):
            merged = []
            for en_b, bn_b in zip(en_blocks, bn_blocks):
                if bn_b.confidence >= en_b.confidence:
                    merged.append(bn_b)
                else:
                    merged.append(en_b)
            return merged

        # Different number of blocks → use the set with more blocks
        # (typically the one that detected more content)
        en_avg = (
            sum(b.confidence for b in en_blocks) / len(en_blocks) if en_blocks else 0
        )
        bn_avg = (
            sum(b.confidence for b in bn_blocks) / len(bn_blocks) if bn_blocks else 0
        )

        if bn_avg >= en_avg:
            return bn_blocks
        return en_blocks

    def get_full_text(self, blocks: List[OCRBlock]) -> str:
        """Combine all blocks into full text."""
        return "\n".join(b.text for b in blocks if b.text.strip())

    def get_average_confidence(self, blocks: List[OCRBlock]) -> float:
        """Get average confidence across all blocks."""
        if not blocks:
            return 0.0
        return sum(b.confidence for b in blocks) / len(blocks)
