"""
OCR Engine — Hybrid OCR with PaddleOCR and EasyOCR support.
Handles both English and Bangla text detection and recognition.
Supports engine selection via config.OCR_ENGINE_PRIORITY.
Speed optimized for Bangla processing.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import config
from .models import BBox, ContentBlock

logger = logging.getLogger(__name__)

# ── Lazy-initialized singletons ───────────────────────────────────────
_easyocr_reader: Any = None
_easyocr_langs: list = []
_paddleocr_reader: Any = None
_active_engine: str = ""


def _init_paddleocr():
    """Initialize PaddleOCR reader (lazy init, cached)."""
    global _paddleocr_reader
    if _paddleocr_reader is not None:
        return _paddleocr_reader

    try:
        from paddleocr import PaddleOCR

        # PaddleOCR supports multilingual models
        # Use PP-OCRv4 for better accuracy with Bengali
        _paddleocr_reader = PaddleOCR(
            use_angle_cls=True,  # Auto-rotate detection
            # Use "en" to activate Paddle's multilingual detector/recognizer path.
            # The Chinese model is not suitable for Bangla-heavy OCR in this project.
            lang="en",
            use_gpu=config.PADDLE_USE_GPU,
            show_log=False,
            enable_mkldnn=True,  # Intel MKL-DNN acceleration
            rec_batch_num=6,  # Batch recognition for speed
            det_db_thresh=0.3,  # Detection threshold
            det_db_box_thresh=0.5,  # Box threshold
        )
        config.set_status("paddleocr_available", True)
        logger.info("PaddleOCR initialized successfully")
        return _paddleocr_reader
    except Exception as e:
        config.set_status("paddleocr_available", False)
        logger.warning("PaddleOCR init failed: %s", e)
        return None


def _init_easyocr():
    """Initialize EasyOCR reader (lazy init, cached)."""
    global _easyocr_reader, _easyocr_langs
    if _easyocr_reader is not None:
        return _easyocr_reader

    try:
        import easyocr

        for langs in [["bn", "en"], ["en"]]:
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
            except Exception as e:
                logger.warning("EasyOCR init with langs=%s failed: %s", langs, e)

        config.set_status("easyocr_available", False)
        return None
    except Exception as e:
        config.set_status("easyocr_available", False)
        logger.warning("EasyOCR init failed: %s", e)
        return None


def _get_active_engine() -> Tuple[str, Any]:
    """Get the active OCR engine based on config priority.
    Returns (engine_name, engine_instance).
    """
    global _active_engine

    for engine_name in config.OCR_ENGINE_PRIORITY:
        if engine_name == "paddleocr":
            reader = _init_paddleocr()
            if reader is not None:
                _active_engine = "paddleocr"
                return ("paddleocr", reader)
        elif engine_name == "easyocr":
            reader = _init_easyocr()
            if reader is not None:
                _active_engine = "easyocr"
                return ("easyocr", reader)

    raise RuntimeError(
        "No OCR engine could be initialized. Install paddleocr or easyocr."
    )


# ── Preprocessing (Speed Optimized) ──────────────────────────────────


def preprocess_image(img_bytes: bytes, fast_mode: bool = False) -> np.ndarray:
    """
    Apply OpenCV preprocessing to improve OCR accuracy.
    Fast mode: Skip expensive operations for Bangla-heavy documents.
    Returns the processed image as a numpy array.
    """
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if fast_mode or config.FAST_MODE:
        # Fast mode: Simple thresholding, skip morphological ops
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    # Standard mode: Adaptive threshold + morphological cleaning
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        8,
    )

    # Morphological cleaning – remove small noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    return cleaned


def preprocess_image_minimal(img_bytes: bytes) -> np.ndarray:
    """Minimal preprocessing - just decode and grayscale. Fastest option."""
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct slight rotation using Hough line detection."""
    coords = np.column_stack(np.where(image < 128))
    if len(coords) < 50:
        return image
    try:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return image
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        rot = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            rot,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return image


# ── Core OCR (Multi-Engine Support) ──────────────────────────────────


def _run_paddleocr(img: np.ndarray) -> List[Tuple[str, float, list]]:
    """Run PaddleOCR on a preprocessed image."""
    reader = _init_paddleocr()
    if reader is None:
        return []

    try:
        # PaddleOCR returns: [[[bbox_points], (text, confidence)], ...]
        results = reader.ocr(img, cls=True)

        detections = []
        if results and results[0]:
            for line in results[0]:
                if line is None:
                    continue
                bbox_points = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text, conf = line[1]
                detections.append((text, float(conf), bbox_points))
        return detections
    except Exception as e:
        logger.error("PaddleOCR failed: %s", e)
        return []


def _run_easyocr(img: np.ndarray) -> List[Tuple[str, float, list]]:
    """Run EasyOCR on a preprocessed image."""
    reader = _init_easyocr()
    if reader is None:
        return []

    try:
        results = reader.readtext(img)
        detections = []
        for result in results:
            bbox_points = result[0]
            text = result[1]
            conf = float(result[2])
            detections.append((text, conf, bbox_points))
        return detections
    except Exception as e:
        logger.error("EasyOCR failed: %s", e)
        return []


def run_ocr(
    img_bytes: bytes, lang: str = "en", fast_mode: bool = False
) -> List[Tuple[str, float, list]]:
    """
    Run OCR on image bytes using the configured engine priority.
    Returns list of (text, confidence, bbox_points).

    Args:
        img_bytes: Raw image bytes
        lang: Language hint ('en', 'bn', 'mixed')
        fast_mode: Use minimal preprocessing for speed
    """
    # Determine if we should use fast mode for Bangla-heavy content
    is_bangla = lang in ("bn", "mixed")
    use_fast = (
        fast_mode
        or config.FAST_MODE
        or (is_bangla and getattr(config, "FAST_MODE_BANGLA", True))
    )

    try:
        if use_fast:
            processed = preprocess_image_minimal(img_bytes)
        else:
            processed = preprocess_image(img_bytes, fast_mode=use_fast)
    except Exception as e:
        logger.warning("Preprocessing failed: %s, using raw image", e)
        nparr = np.frombuffer(img_bytes, np.uint8)
        processed = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if processed is None:
            return []

    # Try engines in priority order
    for engine_name in config.OCR_ENGINE_PRIORITY:
        if engine_name == "paddleocr":
            detections = _run_paddleocr(processed)
            if detections:
                logger.debug("PaddleOCR returned %d detections", len(detections))
                return detections
        elif engine_name == "easyocr":
            detections = _run_easyocr(processed)
            if detections:
                logger.debug("EasyOCR returned %d detections", len(detections))
                return detections

    logger.warning("All OCR engines returned empty results")
    return []


def run_dual_ocr(
    img_bytes: bytes, fast_mode: bool = False
) -> List[Tuple[str, float, list]]:
    """
    Run OCR on image bytes optimized for mixed Bangla/English content.
    Uses fast mode by default for Bangla to improve processing speed.
    """
    return run_ocr(img_bytes, lang="bn", fast_mode=fast_mode)


def get_active_engine_name() -> str:
    """Get the name of the currently active OCR engine."""
    global _active_engine
    if _active_engine:
        return _active_engine

    # Initialize to determine active engine
    try:
        _get_active_engine()
    except Exception:
        pass
    return _active_engine or "none"


def detections_to_blocks(
    detections: List[Tuple[str, float, list]],
    offset: int = 1,
) -> List[ContentBlock]:
    """Convert raw OCR detections into ContentBlock objects."""
    blocks = []
    for i, (text, conf, bbox_pts) in enumerate(detections):
        # Determine language from content
        from .unicode_validator import bangla_char_ratio

        bn_ratio = bangla_char_ratio(text)
        if bn_ratio > 0.5:
            lang = "bn"
        elif bn_ratio > 0.1:
            lang = "mixed"
        else:
            lang = "en"

        # Convert bbox from 4-point to simple rectangle
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
                type="paragraph",  # refined later
                language=lang,
                text=text,
                confidence=conf,
                bbox=bbox,
            )
        )
    return blocks
