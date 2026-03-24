"""EasyOCR engine utilities for Last-Try OCR."""

import logging
from typing import Any, List, Tuple

import cv2
import numpy as np

from .. import config
from ..exceptions import OCREngineError
from ..models import BBox, ContentBlock
from ..nlp.unicode_validator import bangla_char_ratio

logger = logging.getLogger(__name__)

_easyocr_reader: Any = None
_easyocr_langs: list = []
_active_engine: str = ""


def _init_easyocr() -> Any:
    """Initialize and cache EasyOCR reader."""
    global _easyocr_reader, _easyocr_langs
    if _easyocr_reader is not None:
        return _easyocr_reader

    try:
        import easyocr

        for langs in [config.EASYOCR_LANGUAGES, ["en"]]:
            try:
                _easyocr_reader = easyocr.Reader(
                    langs,
                    gpu=config.EASYOCR_USE_GPU,
                    verbose=False,
                )
                _easyocr_langs = langs
                config.set_status("easyocr_available", True)
                logger.info("EasyOCR reader ready (langs=%s)", langs)
                return _easyocr_reader
            except Exception as exc:
                logger.warning("EasyOCR init with langs=%s failed: %s", langs, exc)

        config.set_status("easyocr_available", False)
        raise OCREngineError("EasyOCR failed to initialize for all language sets")
    except Exception as exc:
        config.set_status("easyocr_available", False)
        if isinstance(exc, OCREngineError):
            raise
        raise OCREngineError(f"EasyOCR init failed: {exc}") from exc


def _get_active_engine() -> Tuple[str, Any]:
    """Get active OCR engine tuple (name, instance)."""
    global _active_engine

    if "easyocr" in config.OCR_ENGINE_PRIORITY:
        reader = _init_easyocr()
        _active_engine = "easyocr"
        return "easyocr", reader

    raise OCREngineError("No local OCR engine configured")


def preprocess_image(img_bytes: bytes, fast_mode: bool = False) -> np.ndarray:
    """Preprocess image bytes for OCR."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if fast_mode or config.FAST_MODE:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        8,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)


def preprocess_image_minimal(img_bytes: bytes) -> np.ndarray:
    """Minimal decode + grayscale path."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _run_easyocr(img: np.ndarray) -> List[Tuple[str, float, list]]:
    """Run EasyOCR and return tuple detections."""
    try:
        reader = _init_easyocr()
        results = reader.readtext(img)
    except OCREngineError:
        raise
    except Exception as exc:
        raise OCREngineError(f"EasyOCR readtext failed: {exc}") from exc

    detections: List[Tuple[str, float, list]] = []
    for result in results:
        bbox_points = result[0]
        text = result[1]
        conf = float(result[2])
        detections.append((text, conf, bbox_points))
    return detections


def run_ocr(
    img_bytes: bytes,
    lang: str = "en",
    fast_mode: bool = False,
) -> List[Tuple[str, float, list]]:
    """Run local OCR with EasyOCR."""
    is_bangla = lang in ("bn", "mixed")
    use_fast = (
        fast_mode
        or config.FAST_MODE
        or (is_bangla and getattr(config, "FAST_MODE_BANGLA", True))
    )

    try:
        processed = preprocess_image_minimal(img_bytes) if use_fast else preprocess_image(
            img_bytes,
            fast_mode=use_fast,
        )
    except Exception as exc:
        logger.warning("Preprocessing failed: %s, using raw image", exc)
        nparr = np.frombuffer(img_bytes, np.uint8)
        processed = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if processed is None:
            return []

    detections = _run_easyocr(processed)
    if detections:
        logger.debug("EasyOCR returned %d detections", len(detections))
    else:
        logger.warning("EasyOCR returned empty results")
    return detections


def run_dual_ocr(img_bytes: bytes, fast_mode: bool = False) -> List[Tuple[str, float, list]]:
    """Bangla+English optimized OCR helper."""
    return run_ocr(img_bytes, lang="bn", fast_mode=fast_mode)


def get_active_engine_name() -> str:
    """Get name of active local OCR engine."""
    global _active_engine
    if _active_engine:
        return _active_engine
    try:
        _get_active_engine()
    except Exception:
        return "none"
    return _active_engine or "none"


def detections_to_blocks(
    detections: List[Tuple[str, float, list]],
    offset: int = 1,
) -> List[ContentBlock]:
    """Convert tuple detections to content blocks."""
    blocks: List[ContentBlock] = []
    for i, (text, conf, bbox_pts) in enumerate(detections):
        bn_ratio = bangla_char_ratio(text)
        if bn_ratio > 0.5:
            lang = "bn"
        elif bn_ratio > 0.1:
            lang = "mixed"
        else:
            lang = "en"

        bbox = None
        if bbox_pts:
            xs = [p[0] for p in bbox_pts]
            ys = [p[1] for p in bbox_pts]
            bbox = BBox(
                x1=round(min(xs), 2),
                y1=round(min(ys), 2),
                x2=round(max(xs), 2),
                y2=round(max(ys), 2),
            )

        blocks.append(
            ContentBlock(
                block_id=offset + i,
                type="paragraph",
                language=lang,
                text=text,
                confidence=conf,
                bbox=bbox,
            )
        )
    return blocks
