"""
Gemini Fallback Module.
Used ONLY for low-confidence blocks after correction layer.

Features:
  - Receives only individual low-confidence blocks (never full pages)
  - Token-optimized minimal prompt
  - Content hash caching
  - Retry logic with exponential backoff
  - Strict JSON output
  - Preserves original Bangla exactly
"""

import os
import json
import hashlib
import time
import re
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from PIL import Image

from . import config

logger = logging.getLogger(__name__)

# Cache for Gemini responses (in-memory + disk)
_response_cache: Dict[str, str] = {}


def _get_content_hash(content: str) -> str:
    """Generate hash for content-based caching."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_cache():
    """Load disk cache into memory."""
    global _response_cache
    cache_dir = config.CACHE_DIR / "gemini"
    if not cache_dir.exists():
        return
    for f in cache_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            _response_cache[f.stem] = data.get("response", "")
        except Exception:
            pass


def _save_to_cache(content_hash: str, response: str):
    """Save response to disk cache."""
    if not config.GEMINI_CACHE_ENABLED:
        return
    cache_dir = config.CACHE_DIR / "gemini"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{content_hash}.json"
    cache_file.write_text(
        json.dumps({"hash": content_hash, "response": response}, ensure_ascii=False),
        encoding="utf-8",
    )
    _response_cache[content_hash] = response


def _get_from_cache(content_hash: str) -> Optional[str]:
    """Get cached response if available."""
    if not config.GEMINI_CACHE_ENABLED:
        return None
    if content_hash in _response_cache:
        logger.info(f"Gemini cache hit: {content_hash}")
        return _response_cache[content_hash]
    return None


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from Gemini response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ====================================
# Block-level text correction via Gemini
# ====================================

# Minimal, token-optimized prompt for block correction
_BLOCK_CORRECTION_PROMPT = """Fix OCR errors in this text block. Rules:
1. Preserve original Bangla characters EXACTLY - do NOT translate
2. Fix spelling/OCR errors only
3. Do NOT add, remove, or rearrange content
4. Do NOT modify correct English words
5. Return ONLY the corrected text, nothing else
6. Maintain original formatting

Text block:
{text}"""


def correct_block_with_gemini(
    text: str,
    language_type: str = "unknown",
    client=None,
) -> Optional[str]:
    """
    Send a single low-confidence block to Gemini for correction.

    Args:
        text: The text block to correct
        language_type: Language type hint
        client: google.genai Client instance

    Returns:
        Corrected text or None if failed
    """
    if not text.strip():
        return text

    # Check cache first
    content_hash = _get_content_hash(text)
    cached = _get_from_cache(content_hash)
    if cached is not None:
        return cached

    if client is None:
        try:
            from google import genai

            client = genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Gemini client init failed: {e}")
            return None

    prompt = _BLOCK_CORRECTION_PROMPT.format(text=text)

    # Retry with exponential backoff
    for attempt in range(config.GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[prompt],
            )
            result = response.text.strip()

            # Cache the result
            _save_to_cache(content_hash, result)
            logger.info(f"Gemini corrected block (hash={content_hash})")
            return result

        except Exception as e:
            wait_time = config.GEMINI_RETRY_DELAY * (2**attempt)
            logger.warning(
                f"Gemini attempt {attempt + 1}/{config.GEMINI_MAX_RETRIES} failed: {e}. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    logger.error(f"Gemini correction failed after {config.GEMINI_MAX_RETRIES} attempts")
    return None


# ====================================
# Full-page structured extraction via Gemini (for image-based OCR pages)
# ====================================

_PAGE_EXTRACTION_PROMPT = """Extract ALL text exactly as written.
Extract all visible content from this image in STRICT structured JSON format only.
Preserve original Bangla characters exactly.
Do NOT translate.
Return STRICT valid JSON only.
Do NOT include markdown formatting.
Do NOT include explanations.
Ensure UTF-8 correctness."""


def extract_page_with_gemini(
    image_path: str,
    client=None,
) -> Optional[str]:
    """
    Extract structured content from a page image using Gemini.
    Used when PaddleOCR confidence is very low for the entire page.

    Args:
        image_path: Path to the page image
        client: google.genai Client instance

    Returns:
        Extracted text/JSON or None
    """
    # Check cache
    try:
        with open(image_path, "rb") as f:
            image_hash = hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        image_hash = _get_content_hash(image_path)

    cached = _get_from_cache(image_hash)
    if cached is not None:
        return cached

    if client is None:
        try:
            from google import genai

            client = genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Gemini client init failed: {e}")
            return None

    image = Image.open(image_path)

    for attempt in range(config.GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[_PAGE_EXTRACTION_PROMPT, image],
            )
            result = _clean_json_response(response.text)

            _save_to_cache(image_hash, result)
            logger.info(f"Gemini extracted page (hash={image_hash})")
            return result

        except Exception as e:
            wait_time = config.GEMINI_RETRY_DELAY * (2**attempt)
            logger.warning(
                f"Gemini page extraction attempt {attempt + 1} failed: {e}. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    logger.error("Gemini page extraction failed after retries")
    return None


# Initialize cache on module load
_load_cache()


class GeminiUsageTracker:
    """Track Gemini API usage for cost reporting."""

    def __init__(self):
        self.block_corrections = 0
        self.page_extractions = 0
        self.cache_hits = 0
        self.total_calls = 0
        self.failed_calls = 0

    def record_block_correction(self, cached: bool = False):
        if cached:
            self.cache_hits += 1
        else:
            self.block_corrections += 1
            self.total_calls += 1

    def record_page_extraction(self, cached: bool = False):
        if cached:
            self.cache_hits += 1
        else:
            self.page_extractions += 1
            self.total_calls += 1

    def record_failure(self):
        self.failed_calls += 1

    def to_dict(self) -> dict:
        return {
            "block_corrections": self.block_corrections,
            "page_extractions": self.page_extractions,
            "cache_hits": self.cache_hits,
            "total_api_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "calls_saved_by_cache": self.cache_hits,
        }
