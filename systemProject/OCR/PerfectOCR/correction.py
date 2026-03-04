"""
Bangla Text Correction Module for PerfectOCR.
Runs a post-correction pass on OCR output to fix Bangla character-level errors.
Uses GPT-4o (or configurable model) for intelligent correction.
"""

import logging
import time
from typing import Optional, Dict, Any

from . import config

logger = logging.getLogger(__name__)

# ── CORRECTION PROMPT ───────────────────────────────────
CORRECTION_PROMPT = """This is Bangla OCR output that may have character-level errors.
Fix ONLY genuine OCR mistakes. DO NOT change meaning, translate, or rewrite sentences.
Preserve all English words exactly.

## What to fix:
1. Wrong mattra (মাত্রা) — e.g., "কারু" → "কারো"
2. Missing hasanta (্) — e.g., "সক" → "স্ক"
3. Swapped conjuncts — e.g., "স্ত" → "ত্স" if wrong
4. Bengali numeral errors — CRITICAL: 
   - ৩ (3) and ৫ (5) are commonly swapped
   - ৮ (8) and ৪ (4) are commonly swapped
   - Verify dates make sense: month ≤ 12, day ≤ 31
   - If a date looks wrong (e.g., ১৩ month), consider if ১৫ was meant
5. Word-level corrections — if a Bangla word is clearly misspelled due to OCR, fix it
6. Preserve "[Signature ...]", "[ILLEGIBLE]" markers exactly as they are

Return ONLY the corrected text, nothing else.

Text:
{text}"""


def correct_bangla_text(
    raw_text: str,
    model: str = None,
) -> str:
    """
    Run a correction pass on OCR output to fix Bangla text errors.

    Args:
        raw_text: The OCR extracted text
        model: Model to use (default from config)

    Returns:
        Corrected text
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    if not config.ENABLE_BANGLA_CORRECTION:
        return raw_text

    # Check if text contains any Bangla characters
    has_bangla = any(
        config.BANGLA_UNICODE_START <= ord(ch) <= config.BANGLA_UNICODE_END
        for ch in raw_text
    )
    if not has_bangla:
        logger.debug("No Bangla characters found, skipping correction")
        return raw_text

    model = model or config.CORRECTION_MODEL

    try:
        if _is_openai_model(model):
            return _correct_with_openai(raw_text, model)
        else:
            return _correct_with_gemini(raw_text, model)
    except Exception as e:
        logger.warning(f"Correction failed: {e}. Returning original text.")
        return raw_text


def _is_openai_model(model: str) -> bool:
    """Check if model string refers to an OpenAI model."""
    return model.startswith("gpt") or model.startswith("o1") or model.startswith("o3")


def _correct_with_openai(text: str, model: str) -> str:
    """Correct text using OpenAI API."""
    from openai import OpenAI

    kwargs = {"api_key": config.OPENAI_API_KEY}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    client = OpenAI(**kwargs)

    prompt = CORRECTION_PROMPT.format(text=text)

    for attempt in range(config.OPENAI_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=min(len(text) * 2, config.OPENAI_MAX_TOKENS),
            )
            corrected = response.choices[0].message.content.strip()
            logger.info(f"Bangla correction complete (OpenAI {model})")
            return corrected

        except Exception as e:
            wait_time = config.OPENAI_RETRY_DELAY * (2**attempt)
            logger.warning(
                f"Correction attempt {attempt + 1} failed: {e}. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    logger.error("Bangla correction failed after all retries")
    return text


def _correct_with_gemini(text: str, model: str) -> str:
    """Correct text using Gemini API."""
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = CORRECTION_PROMPT.format(text=text)

    for attempt in range(config.GEMINI_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
            )
            corrected = response.text.strip()
            logger.info(f"Bangla correction complete (Gemini {model})")
            return corrected

        except Exception as e:
            wait_time = config.GEMINI_RETRY_DELAY * (2**attempt)
            logger.warning(
                f"Correction attempt {attempt + 1} failed: {e}. "
                f"Retrying in {wait_time}s..."
            )
            time.sleep(wait_time)

    logger.error("Bangla correction failed after all retries")
    return text
