"""
Language Detection Module.
Detects whether text blocks are Bangla-heavy, English-heavy, or Mixed.
Uses Unicode range analysis and character ratio calculation.
"""

import re
import logging
from typing import Tuple

from . import config
from .models import LanguageType

logger = logging.getLogger(__name__)

# Bangla Unicode range: U+0980 – U+09FF
_BANGLA_PATTERN = re.compile(r"[\u0980-\u09FF]")
# English letters
_ENGLISH_PATTERN = re.compile(r"[a-zA-Z]")
# Digits (shared)
_DIGIT_PATTERN = re.compile(r"[0-9\u09E6-\u09EF]")  # ASCII + Bangla digits
# Punctuation & whitespace (neutral)
_NEUTRAL_PATTERN = re.compile(r"[\s\d\W]", re.UNICODE)


def detect_language(text: str) -> Tuple[LanguageType, float, float]:
    """
    Detect language type of a text block.

    Returns:
        (language_type, bangla_ratio, english_ratio)
    """
    if not text or not text.strip():
        return LanguageType.UNKNOWN, 0.0, 0.0

    # Count characters
    bangla_chars = len(_BANGLA_PATTERN.findall(text))
    english_chars = len(_ENGLISH_PATTERN.findall(text))

    # Only count meaningful characters (exclude whitespace, digits, punctuation)
    total_meaningful = bangla_chars + english_chars
    if total_meaningful == 0:
        return LanguageType.UNKNOWN, 0.0, 0.0

    bangla_ratio = bangla_chars / total_meaningful
    english_ratio = english_chars / total_meaningful

    # Classify
    if bangla_ratio >= config.BANGLA_HEAVY_THRESHOLD:
        lang_type = LanguageType.BANGLA_HEAVY
    elif english_ratio >= config.ENGLISH_HEAVY_THRESHOLD:
        lang_type = LanguageType.ENGLISH_HEAVY
    elif (
        bangla_ratio >= config.MIXED_THRESHOLD
        and english_ratio >= config.MIXED_THRESHOLD
    ):
        lang_type = LanguageType.MIXED
    elif bangla_ratio > english_ratio:
        lang_type = LanguageType.BANGLA_HEAVY
    elif english_ratio > bangla_ratio:
        lang_type = LanguageType.ENGLISH_HEAVY
    else:
        lang_type = LanguageType.UNKNOWN

    return lang_type, round(bangla_ratio, 4), round(english_ratio, 4)


def get_bangla_char_count(text: str) -> int:
    """Count Bangla Unicode characters."""
    return len(_BANGLA_PATTERN.findall(text))


def get_english_char_count(text: str) -> int:
    """Count English alphabet characters."""
    return len(_ENGLISH_PATTERN.findall(text))


def has_bangla(text: str) -> bool:
    """Check if text contains any Bangla characters."""
    return bool(_BANGLA_PATTERN.search(text))


def has_english(text: str) -> bool:
    """Check if text contains any English characters."""
    return bool(_ENGLISH_PATTERN.search(text))


def calculate_page_language_distribution(blocks_languages: list) -> dict:
    """
    Calculate language distribution across page blocks.

    Args:
        blocks_languages: List of (LanguageType, bangla_ratio, english_ratio) tuples

    Returns:
        Dict with distribution percentages
    """
    if not blocks_languages:
        return {"bangla": 0.0, "english": 0.0, "mixed": 0.0, "unknown": 0.0}

    counts = {
        "bangla": 0,
        "english": 0,
        "mixed": 0,
        "unknown": 0,
    }

    for lang_type, _, _ in blocks_languages:
        if lang_type == LanguageType.BANGLA_HEAVY:
            counts["bangla"] += 1
        elif lang_type == LanguageType.ENGLISH_HEAVY:
            counts["english"] += 1
        elif lang_type == LanguageType.MIXED:
            counts["mixed"] += 1
        else:
            counts["unknown"] += 1

    total = len(blocks_languages)
    return {k: round(v / total, 4) for k, v in counts.items()}
