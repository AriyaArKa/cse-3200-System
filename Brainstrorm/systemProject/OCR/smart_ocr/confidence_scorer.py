"""
Composite Confidence Scoring Module.
Calculates weighted confidence score for each text block.
Uses multiple signals: OCR confidence, unicode ratio, dictionary match,
invalid char ratio, regex validation, and structural consistency.
"""

import re
import logging
from typing import List, Optional

from . import config
from .models import LanguageType, RoutingDecision

logger = logging.getLogger(__name__)

# Common Bangla words for dictionary matching
_BANGLA_COMMON_WORDS = {
    "এবং",
    "করা",
    "হয়",
    "থেকে",
    "তার",
    "একটি",
    "আমি",
    "আপনি",
    "সকল",
    "জন্য",
    "প্রতি",
    "বিষয়",
    "কাজ",
    "দিন",
    "সময়",
    "বছর",
    "মাস",
    "তারিখ",
    "নম্বর",
    "অনুসারে",
    "অনুযায়ী",
    "পরিচালক",
    "বিশ্ববিদ্যালয়",
    "বিভাগ",
    "শিক্ষক",
    "শিক্ষার্থী",
    "কর্মকর্তা",
    "কর্মচারী",
    "অফিস",
    "দপ্তর",
    "সভাপতি",
    "সদস্য",
    "কমিটি",
    "নোটিশ",
    "বিজ্ঞপ্তি",
    "আদেশ",
    "পত্র",
    "স্মারক",
    "অনুলিপি",
    "প্রেরণ",
    "অবগতি",
    "প্রয়োজনীয়",
    "ব্যবস্থা",
    "গ্রহণ",
    "তিনি",
    "তাদের",
    "আমরা",
    "তোমার",
    "এই",
    "সেই",
    "যে",
    "কি",
    "কেন",
    "কোথায়",
    "কখন",
    "কিভাবে",
    "হলো",
    "হয়েছে",
    "করতে",
    "বলে",
    "নেই",
    "আছে",
    "ছিল",
    "হবে",
    "করে",
    "দিয়ে",
    "নিয়ে",
}

# Common English words
_ENGLISH_COMMON_WORDS = {
    "the",
    "and",
    "for",
    "are",
    "but",
    "not",
    "you",
    "all",
    "can",
    "her",
    "was",
    "one",
    "our",
    "out",
    "day",
    "had",
    "has",
    "his",
    "how",
    "its",
    "may",
    "new",
    "now",
    "old",
    "see",
    "way",
    "who",
    "did",
    "get",
    "let",
    "say",
    "she",
    "too",
    "use",
    "from",
    "have",
    "this",
    "will",
    "with",
    "that",
    "they",
    "been",
    "date",
    "name",
    "number",
    "page",
    "subject",
    "office",
    "department",
    "university",
    "notice",
}

# Invalid character patterns (likely OCR errors)
_INVALID_CHAR_PATTERN = re.compile(
    r"[^\u0000-\u007F\u0980-\u09FF\u2000-\u206F\u0964-\u0965\s]"
)

# Structural patterns for validation
_BANGLA_MATRA_PATTERN = re.compile(r"[\u09BE-\u09CC\u09D7\u09CD]")
_DATE_PATTERN = re.compile(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}")
_NUMBER_PATTERN = re.compile(r"\d+")


def calculate_confidence(
    text: str,
    ocr_confidence: float = 0.0,
    bangla_ratio: float = 0.0,
    english_ratio: float = 0.0,
    language_type: str = LanguageType.UNKNOWN.value,
) -> float:
    """
    Calculate composite confidence score for a text block.

    Weighted formula:
      score = w1*ocr_conf + w2*unicode_score + w3*dict_score
            + w4*(1-invalid_ratio) + w5*regex_score + w6*structural_score

    Returns: confidence score between 0.0 and 1.0
    """
    if not text.strip():
        return 0.0

    # 1. OCR engine confidence (normalized to 0-1)
    ocr_score = min(max(ocr_confidence, 0.0), 1.0)

    # 2. Unicode ratio score
    unicode_score = _calculate_unicode_score(text)

    # 3. Dictionary match score
    dict_score = _calculate_dictionary_score(text, language_type)

    # 4. Invalid character ratio (inverted — fewer invalid = better)
    invalid_ratio = _calculate_invalid_char_ratio(text)
    invalid_score = 1.0 - invalid_ratio

    # 5. Regex validation score
    regex_score = _calculate_regex_score(text, language_type)

    # 6. Structural consistency score
    structural_score = _calculate_structural_score(text, language_type)

    # Weighted sum
    confidence = (
        config.WEIGHT_OCR_CONFIDENCE * ocr_score
        + config.WEIGHT_UNICODE_RATIO * unicode_score
        + config.WEIGHT_DICTIONARY_MATCH * dict_score
        + config.WEIGHT_INVALID_CHAR_RATIO * invalid_score
        + config.WEIGHT_REGEX_VALIDATION * regex_score
        + config.WEIGHT_STRUCTURAL_CONSISTENCY * structural_score
    )

    return round(min(max(confidence, 0.0), 1.0), 4)


def get_routing_decision(
    confidence: float,
    language_type: str = LanguageType.UNKNOWN.value,
) -> RoutingDecision:
    """
    Determine routing based on confidence and language type.
    Bangla-heavy blocks use stricter thresholds.
    """
    if language_type == LanguageType.BANGLA_HEAVY.value:
        high = config.BANGLA_HIGH_CONFIDENCE
        medium = config.BANGLA_MEDIUM_CONFIDENCE
    else:
        high = config.HIGH_CONFIDENCE_THRESHOLD
        medium = config.MEDIUM_CONFIDENCE_THRESHOLD

    if confidence >= high:
        return RoutingDecision.ACCEPT
    elif confidence >= medium:
        return RoutingDecision.LOCAL_CORRECTION
    else:
        return RoutingDecision.GEMINI_FALLBACK


def _calculate_unicode_score(text: str) -> float:
    """Score based on valid unicode character ratio."""
    if not text:
        return 0.0

    valid = 0
    total = len(text)
    for ch in text:
        cp = ord(ch)
        if (
            config.BANGLA_UNICODE_START <= cp <= config.BANGLA_UNICODE_END
            or 0x0020 <= cp <= 0x007E
            or ch in "\n\r\t "
        ):
            valid += 1
    return valid / total if total > 0 else 0.0


def _calculate_dictionary_score(text: str, language_type: str) -> float:
    """Score based on known word matches."""
    words = re.findall(r"[\u0980-\u09FF]+|[a-zA-Z]+", text.lower())
    if not words:
        return 0.0

    matches = 0
    for word in words:
        if word in _BANGLA_COMMON_WORDS or word in _ENGLISH_COMMON_WORDS:
            matches += 1

    return min(matches / len(words), 1.0)


def _calculate_invalid_char_ratio(text: str) -> float:
    """Calculate ratio of characters that are likely OCR errors."""
    if not text:
        return 0.0
    invalid = len(_INVALID_CHAR_PATTERN.findall(text))
    return invalid / len(text)


def _calculate_regex_score(text: str, language_type: str) -> float:
    """Score based on regex pattern validation (dates, numbers, structure)."""
    score = 0.5  # baseline

    # Boost if text has recognizable patterns
    if _DATE_PATTERN.search(text):
        score += 0.2
    if _NUMBER_PATTERN.search(text):
        score += 0.1

    # For Bangla text, check matra patterns (valid Bangla writing)
    if language_type in (LanguageType.BANGLA_HEAVY.value, LanguageType.MIXED.value):
        bangla_chars = re.findall(r"[\u0980-\u09FF]", text)
        matra_chars = _BANGLA_MATRA_PATTERN.findall(text)
        if bangla_chars:
            matra_ratio = len(matra_chars) / len(bangla_chars)
            # Typical Bangla text has ~20-40% matra/dependent vowels
            if 0.1 <= matra_ratio <= 0.5:
                score += 0.2

    return min(score, 1.0)


def _calculate_structural_score(text: str, language_type: str) -> float:
    """Score based on structural consistency (sentence-like patterns)."""
    score = 0.5

    lines = text.strip().split("\n")
    if not lines:
        return score

    # Check for reasonable line lengths
    avg_line_len = sum(len(l) for l in lines) / len(lines)
    if 10 <= avg_line_len <= 500:
        score += 0.2

    # Check for sentence-ending punctuation
    if re.search(r"[।.!?]\s*$", text):
        score += 0.15

    # Check for consistent spacing
    if not re.search(r"  {3,}", text):  # No excessive spaces
        score += 0.15

    return min(score, 1.0)
