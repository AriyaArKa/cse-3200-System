"""Surya OCR primary engine for BanglaDOC."""

import io
import logging
import os
import re

from PIL import Image

from bangladoc_ocr import config
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

logger = logging.getLogger(__name__)

_foundation = None
_detector = None
_recognizer = None
_load_attempted = False
_available = False

_HTML_TAG = re.compile(r"<[^>]+>")
_NOISE_WORDS = frozenset({"HERE", "SEAL", "COPY", "STAMP"})
_DEVANAGARI_START = 0x0900
_DEVANAGARI_END = 0x097F


def is_available() -> bool:
    return _available


def load() -> bool:
    """Load Surya models once."""
    global _foundation, _detector, _recognizer, _load_attempted, _available
    if _load_attempted:
        return _available

    _load_attempted = True
    try:
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor

        logger.info("Loading Surya models...")
        _foundation = FoundationPredictor()
        _detector = DetectionPredictor()
        _recognizer = RecognitionPredictor(_foundation)
        _available = True
        config.set_status("surya_available", True)
        logger.info("Surya ready")
    except Exception as exc:
        _available = False
        config.set_status("surya_available", False)
        logger.warning("Surya unavailable, fallback chain will continue: %s", exc)

    return _available


def ocr_bytes(img_bytes: bytes) -> str:
    """OCR image bytes with Surya. Returns empty text on failure."""
    if not config.SURYA_ENABLED or not load():
        return ""

    try:
        from surya.common.surya.schema import TaskNames

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        preds = _recognizer(
            [img],
            task_names=[TaskNames.ocr_with_boxes],
            det_predictor=_detector,
            highres_images=[img],
            math_mode=False,
        )
        lines = [line.text for line in preds[0].text_lines]
        text = _clean(lines)
        if _looks_like_wrong_script(text):
            logger.warning(
                "Surya produced Devanagari-heavy text for Bangla pipeline; forcing fallback"
            )
            return ""
        return text
    except Exception as exc:
        logger.warning("Surya page OCR failed: %s", exc)
        return ""


def _clean(lines: list[str]) -> str:
    cleaned: list[str] = []
    for line in lines:
        text = _HTML_TAG.sub("", line).strip()
        if not text:
            continue
        if text.upper() in _NOISE_WORDS and len(text.split()) == 1:
            continue
        cleaned.append(text)
    return "\n".join(cleaned)


def _looks_like_wrong_script(text: str) -> bool:
    if not text:
        return False

    alpha = [ch for ch in text if ch.isalpha()]
    if len(alpha) < 12:
        return False

    devanagari_count = sum(
        1 for ch in alpha if _DEVANAGARI_START <= ord(ch) <= _DEVANAGARI_END
    )
    devanagari_ratio = devanagari_count / len(alpha)
    bangla_ratio = bangla_char_ratio(text)

    return (
        devanagari_ratio >= config.SURYA_DEVANAGARI_REJECT_THRESHOLD
        and bangla_ratio < config.SURYA_MIN_BANGLA_RATIO
    )
