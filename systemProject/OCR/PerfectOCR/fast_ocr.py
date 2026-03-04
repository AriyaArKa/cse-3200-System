"""
Fast OCR Engine using Tesseract for simple/English-only documents.
Only calls expensive AI models when needed (Bangla, handwriting, tables, low confidence).
"""

import logging
import base64
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Check if pytesseract is available
try:
    import pytesseract
    from PIL import Image
    import io

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning(
        "pytesseract not installed. Fast OCR will be disabled. Install with: pip install pytesseract pillow"
    )


class FastOCREngine:
    """
    Fast local OCR using Tesseract.
    Only for simple printed text (primarily English).
    """

    def __init__(self):
        if not TESSERACT_AVAILABLE:
            raise RuntimeError("pytesseract is not installed")
        # Test if tesseract is actually available
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            raise RuntimeError(
                f"Tesseract not found. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki"
            ) from e

    def extract_page(self, image_b64: str, page_num: int) -> Dict[str, Any]:
        """
        Extract text using Tesseract OCR.

        Args:
            image_b64: Base64-encoded PNG image
            page_num: Page number (1-indexed)

        Returns:
            Structured OCR result dict with confidence data
        """
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_bytes))

            # Run Tesseract with detailed data
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT, lang="eng"
            )

            # Extract text with confidence
            full_text = pytesseract.image_to_string(image, lang="eng")

            # Calculate average confidence
            confidences = [int(conf) for conf in data["conf"] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Build content blocks from Tesseract data
            content_blocks = []
            block_id = 1
            n_boxes = len(data["text"])

            for i in range(n_boxes):
                text = data["text"][i].strip()
                if not text:
                    continue

                conf = int(data["conf"][i])
                if conf < 0:
                    continue

                # Convert confidence to our scale
                if conf >= 85:
                    conf_level = "high"
                elif conf >= 60:
                    conf_level = "medium"
                else:
                    conf_level = "low"

                content_blocks.append(
                    {
                        "block_id": block_id,
                        "type": "paragraph",
                        "position": "middle",
                        "language": "en",
                        "confidence": conf_level,
                        "text": text,
                        "is_handwritten": False,
                        "_tesseract_confidence": conf,
                    }
                )
                block_id += 1

            result = {
                "page_number": page_num,
                "content_blocks": content_blocks,
                "tables": [],
                "forms": [],
                "full_text_reading_order": full_text.strip(),
                "extraction_notes": [],
                "_avg_tesseract_confidence": avg_confidence,
            }

            logger.info(
                f"Tesseract extracted page {page_num} (avg confidence: {avg_confidence:.1f}%)"
            )
            return result

        except Exception as e:
            logger.error(f"Tesseract OCR failed for page {page_num}: {e}")
            return {
                "page_number": page_num,
                "content_blocks": [],
                "tables": [],
                "forms": [],
                "full_text_reading_order": "",
                "extraction_notes": [f"Tesseract OCR failed: {str(e)}"],
                "_avg_tesseract_confidence": 0,
            }


def should_use_ai_ocr(tesseract_result: Dict[str, Any]) -> bool:
    """
    Determine if we should use expensive AI OCR based on Tesseract results.

    Uses AI OCR when:
    - Average confidence is low (< 75%)
    - Very little text extracted (< 50 chars)
    - Text contains non-Latin scripts (potential Bangla)
    - Complex layout detected (potential tables)

    Args:
        tesseract_result: Result from Tesseract OCR

    Returns:
        True if AI OCR should be used, False if Tesseract is good enough
    """
    avg_conf = tesseract_result.get("_avg_tesseract_confidence", 0)
    full_text = tesseract_result.get("full_text_reading_order", "")

    # Low confidence - use AI
    if avg_conf < 75:
        logger.info(f"Using AI OCR: low Tesseract confidence ({avg_conf:.1f}%)")
        return True

    # Too little text - might be handwriting or complex layout
    if len(full_text) < 50:
        logger.info(f"Using AI OCR: too little text extracted ({len(full_text)} chars)")
        return True

    # Check for non-Latin characters (Bangla, etc.)
    has_non_latin = any(ord(c) > 0x024F for c in full_text if not c.isspace())
    if has_non_latin:
        logger.info("Using AI OCR: non-Latin characters detected")
        return True

    # Check if mostly low-confidence blocks
    low_conf_blocks = sum(
        1
        for b in tesseract_result.get("content_blocks", [])
        if b.get("confidence") == "low"
    )
    total_blocks = len(tesseract_result.get("content_blocks", []))

    if total_blocks > 0 and (low_conf_blocks / total_blocks) > 0.3:
        logger.info(
            f"Using AI OCR: too many low-confidence blocks ({low_conf_blocks}/{total_blocks})"
        )
        return True

    # Tesseract result is good enough
    logger.info(
        f"Using Tesseract result: confidence {avg_conf:.1f}%, {len(full_text)} chars extracted"
    )
    return False
