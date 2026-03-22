"""Gemini OCR fallback call."""

import io
import logging
import time
from typing import Optional

from bangladoc_ocr import config

from .state import API_STATS

logger = logging.getLogger(__name__)


def ocr_with_gemini(img_bytes: bytes, page_number: int, prompt: str) -> Optional[str]:
    if not config.GEMINI_ENABLED or not config.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from PIL import Image

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if max(image.size) > config.MAX_IMAGE_DIMENSION:
            image.thumbnail((config.MAX_IMAGE_DIMENSION, config.MAX_IMAGE_DIMENSION), Image.LANCZOS)

        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[prompt, image],
                )
                text = (response.text or "").strip()
                if text:
                    API_STATS["gemini_calls"] += 1
                    API_STATS["total_calls"] += 1
                    tokens = getattr(getattr(response, "usage_metadata", None), "total_token_count", 0)
                    API_STATS["gemini_tokens"] += tokens
                    API_STATS["total_tokens"] += tokens
                    logger.info("Gemini page %s: %d chars", page_number, len(text))
                    return text
            except Exception:
                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    time.sleep(config.GEMINI_RETRY_DELAY)
                else:
                    raise

        API_STATS["gemini_errors"] += 1
        return None
    except Exception as exc:
        logger.warning("Gemini OCR failed on page %s: %s", page_number, exc)
        API_STATS["gemini_errors"] += 1
        return None
