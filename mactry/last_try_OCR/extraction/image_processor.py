"""
Image Processor — Extract and describe embedded images from PDF pages.
Uses PyMuPDF for extraction. For large images, uses Gemini for description;
small images get a simple heuristic description (no slow local OCR).
"""

import io
import logging
from pathlib import Path
from typing import List

from PIL import Image

from .. import config
from ..models import ImageResult

logger = logging.getLogger(__name__)

# Skip local OCR for images larger than this (pixels)
_MAX_LOCAL_OCR_PIXELS = 500_000  # ~700x700


def classify_image(width: int, height: int, text: str) -> str:
    """Heuristic image type classification."""
    ratio = width / max(height, 1)
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["chart", "graph", "axis", "%"]):
        return "chart"
    if any(kw in text_lower for kw in ["diagram", "flow", "arrow"]):
        return "diagram"
    if ratio > 2.0 or ratio < 0.5:
        return "diagram"
    return "photo"


def process_page_images(
    page_images: list,  # output from pdf_router.extract_page_images
    page_number: int,
    output_dir: Path,
) -> List[ImageResult]:
    """
    Process extracted images: save, describe, classify.
    Skips slow local OCR — uses Gemini for large images.
    """
    results = []

    page_dir = output_dir / str(page_number)
    page_dir.mkdir(parents=True, exist_ok=True)

    for idx, img_data in enumerate(page_images):
        image_id = idx + 1
        img_bytes = img_data["image_bytes"]
        ext = img_data.get("ext", "png")
        width = img_data.get("width", 0)
        height = img_data.get("height", 0)
        pixels = width * height

        # Save image
        img_path = page_dir / f"image_{image_id}.{ext}"
        img_path.write_bytes(img_bytes)

        detected_text = ""

        if pixels > _MAX_LOCAL_OCR_PIXELS:
            # Large image — use Gemini for description (fast)
            detected_text = _describe_image_gemini(img_bytes)
        # Small images — just describe by dimensions, no OCR

        # Classify
        img_type = classify_image(width, height, detected_text)

        # Generate description
        description = _generate_description(img_type, detected_text, width, height)

        # Confidence
        conf = 0.85 if detected_text else 0.60

        results.append(
            ImageResult(
                image_id=image_id,
                type=img_type,
                detected_text=detected_text,
                description=description,
                confidence=conf,
            )
        )

    return results


def _describe_image_gemini(img_bytes: bytes) -> str:
    """Use Gemini to describe/OCR an embedded image. Fast and accurate."""
    try:
        if not config.GEMINI_API_KEY:
            return ""

        from google import genai

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = Image.open(io.BytesIO(img_bytes))

        # Resize if too large to keep API fast
        max_dim = 1024
        if max(image.size) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.LANCZOS)

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                "Describe this image briefly. If it contains text, extract the text. "
                "If it's a logo/seal/emblem, describe what it shows. "
                "If it's a photo, describe the subject. Keep it under 100 words.",
                image,
            ],
        )
        return (response.text or "").strip()[:500]
    except Exception as e:
        logger.warning("Gemini image description failed: %s", e)
        return ""


def _generate_description(
    img_type: str,
    text: str,
    width: int,
    height: int,
) -> str:
    """Generate a text description of the image."""
    size_desc = f"{width}x{height}" if width and height else "unknown size"
    if img_type == "chart":
        desc = f"A chart image ({size_desc})"
        if text:
            desc += f" containing text: {text[:200]}"
    elif img_type == "diagram":
        desc = f"A diagram ({size_desc})"
        if text:
            desc += f" with labels: {text[:200]}"
    else:
        desc = f"A photograph or image ({size_desc})"
        if text:
            desc += f" with embedded text: {text[:200]}"
    return desc
