"""
Bangla Corrector — Multi-stage correction for Bangla OCR text.

Stage A: Unicode normalization
Stage B: Dictionary validation (lightweight)
Stage C: Pattern-based correction (matra, hasanta, conjuncts)
Stage D: Gemini LLM validation & correction (for low-validity text)
"""

import logging
import re
import unicodedata
from pathlib import Path
from typing import Tuple

from .. import config
from .unicode_validator import bangla_char_ratio

logger = logging.getLogger(__name__)

# ── Common Bangla OCR substitution errors ────────────────────────────

_BANGLA_CORRECTIONS = {
    # Common matra errors
    "\u09be\u09be": "\u09be",  # double aa-kaar
    "\u09c7\u09c7": "\u09c7",  # double e-kaar
    "\u09cb\u09cb": "\u09cb",  # double o-kaar
}

# Bangla digit mapping for validation
_BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯"
_ASCII_DIGITS = "0123456789"

# Invisible / zero-width characters to remove
_INVISIBLE_CHARS = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]")

# Valid Bangla combining marks
_BANGLA_COMBINING = set(range(0x09BE, 0x09CE))  # matras
_BANGLA_COMBINING.update(range(0x09D7, 0x09D8))  # au length mark
_BANGLA_COMBINING.add(0x09CD)  # hasanta


# ── Stage A: Unicode Normalization ───────────────────────────────────


def normalize_unicode(text: str) -> str:
    """NFC normalize and clean invisible characters."""
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE_CHARS.sub("", text)
    return text


def fix_combining_sequences(text: str) -> str:
    """
    Fix invalid combining character sequences.
    A combining mark (category M) without a preceding base char is removed.
    """
    result = []
    prev_is_base = False
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("M"):
            if prev_is_base:
                result.append(ch)
            # else: drop orphan combining mark
        else:
            result.append(ch)
            prev_is_base = cat.startswith("L") or cat.startswith("N")
    return "".join(result)


# ── Stage B: Dictionary Validation (lightweight) ─────────────────────

# Fallback set when external wordlist file is unavailable.
_FALLBACK_COMMON_BANGLA_WORDS = {
    "এবং",
    "তার",
    "এই",
    "একটি",
    "করা",
    "হয়",
    "থেকে",
    "পর",
    "সাথে",
    "জন্য",
    "কিন্তু",
    "যে",
    "না",
    "তা",
    "আর",
    "এক",
    "দুই",
    "তিন",
    "বছর",
    "সালে",
    "মধ্যে",
    "পরে",
    "দিন",
    "কাজ",
    "সময়",
    "প্রতি",
    "সকল",
    "সব",
    "মানুষ",
    "বাংলাদেশ",
    "সরকার",
    "শিক্ষা",
    "বিশ্ববিদ্যালয়",
    "বিভাগ",
    "জেলা",
    "উপজেলা",
    "প্রকল্প",
    "কমিটি",
    "সদস্য",
    "সভাপতি",
    "পরিচালক",
    "মন্ত্রণালয়",
    "অফিস",
    "নম্বর",
    "তারিখ",
    "বিষয়",
    "অনুমোদন",
    "প্রেরক",
    "প্রাপক",
    "স্মারক",
    "নং",
    "শাখা",
    "অনুচ্ছেদ",
    "প্রধান",
    "মাধ্যমিক",
    "উচ্চ",
    "পরীক্ষা",
    "ফলাফল",
    "নিয়োগ",
    "বেতন",
    "ভাতা",
    "পদ",
    "পদবি",
    "জাতীয়",
    "ক্রমিক",
}


def _load_common_bangla_words() -> set[str]:
    """Load common Bangla words from bangla_wordlist.txt, else fallback set."""
    wordlist_path = (
        Path(__file__).resolve().parent.parent / "assets" / "bangla_wordlist.txt"
    )
    try:
        if wordlist_path.exists():
            with open(wordlist_path, "r", encoding="utf-8") as f:
                words = {line.strip() for line in f if line.strip() and not line.startswith("#")}
            if words:
                logger.info("Loaded %d Bangla words from %s", len(words), wordlist_path)
                return words
            logger.warning("Bangla wordlist is empty at %s; using fallback set", wordlist_path)
    except Exception as e:
        logger.warning("Failed to load Bangla wordlist %s: %s", wordlist_path, e)

    logger.info("Using fallback Bangla word set (%d words)", len(_FALLBACK_COMMON_BANGLA_WORDS))
    return set(_FALLBACK_COMMON_BANGLA_WORDS)


_COMMON_BANGLA_WORDS = _load_common_bangla_words()


def compute_word_validity(text: str) -> float:
    """
    Compute the ratio of known Bangla words in the text.
    Returns a value 0.0–1.0.
    """
    words = text.split()
    bangla_words = [
        w
        for w in words
        if any(
            config.BANGLA_UNICODE_START <= ord(ch) <= config.BANGLA_UNICODE_END
            for ch in w
        )
    ]
    if not bangla_words:
        return 1.0  # no Bangla words, can't assess
    known = sum(1 for w in bangla_words if w in _COMMON_BANGLA_WORDS)
    return known / len(bangla_words) if bangla_words else 1.0


# ── Stage C: Pattern-based Correction ────────────────────────────────


def fix_matra_errors(text: str) -> str:
    """Fix doubled/misplaced Bangla matras."""
    for wrong, right in _BANGLA_CORRECTIONS.items():
        text = text.replace(wrong, right)
    # Also collapse any repeated identical Bangla vowel signs.
    text = re.sub(r"([\u09be-\u09cc])\1+", r"\1", text)
    return text


def fix_hasanta(text: str) -> str:
    """
    Fix hasanta (্) placement issues:
    - Remove hasanta at start of word
    - Remove double hasanta
    """
    # Double hasanta
    text = text.replace("\u09cd\u09cd", "\u09cd")
    # Hasanta at start of word (after space or start)
    text = re.sub(r"(?<=\s)\u09CD", "", text)
    if text.startswith("\u09cd"):
        text = text[1:]
    return text


def fix_digit_consistency(text: str) -> str:
    """
    In a predominantly Bangla context, if English digits appear
    mixed with Bangla digits in the same token, normalize to Bangla.
    """
    # Only apply in Bangla-heavy text
    if bangla_char_ratio(text) < 0.3:
        return text

    def _fix_token(match: re.Match) -> str:
        token = match.group(0)
        has_bn_digit = any(ch in _BANGLA_DIGITS for ch in token)
        has_en_digit = any(ch in _ASCII_DIGITS for ch in token)

        if has_bn_digit and has_en_digit:
            # Mixed digits in one token — normalize to Bangla
            result = []
            for ch in token:
                if ch in _ASCII_DIGITS:
                    result.append(_BANGLA_DIGITS[_ASCII_DIGITS.index(ch)])
                else:
                    result.append(ch)
            return "".join(result)
        return token

    return re.sub(r"\S+", _fix_token, text)


# ── Main Correction Pipeline ────────────────────────────────────────


def validate_bangla_with_gemini(text: str) -> Tuple[str, bool]:
    """
    Stage D: Send Bangla text to Gemini for validation and correction.
    Returns (corrected_text, was_corrected).
    Only called when word validity is very low (< 0.15).
    """
    if not config.GEMINI_API_KEY or len(text) < 20:
        return text, False

    try:
        from google import genai

        client = genai.Client(api_key=config.GEMINI_API_KEY)

        prompt = (
            "You are a Bangla language expert. The following text was extracted via OCR "
            "and may contain errors in Bangla characters, matras, conjuncts, or numerals.\n\n"
            "Fix ONLY obvious OCR errors in the Bangla text. Do NOT change meaning, "
            "do NOT translate, do NOT add new content. If the text looks correct, "
            "return it unchanged.\n\n"
            "Rules:\n"
            "- Fix broken conjuncts (যুক্তবর্ণ)\n"
            "- Fix wrong matras (কার চিহ্ন)\n"
            "- Fix hasanta placement\n"
            "- Preserve all English text, numbers, and formatting exactly\n"
            "- Return ONLY the corrected text, nothing else\n\n"
            f"Text:\n{text[:2000]}"
        )

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[prompt],
        )

        corrected = (response.text or "").strip()
        if corrected and len(corrected) > len(text) * 0.5:
            was_changed = corrected != text
            return corrected, was_changed
        return text, False

    except Exception as e:
        logger.warning("Gemini Bangla validation failed: %s", e)
        return text, False


def correct_bangla_text(text: str) -> Tuple[str, dict]:
    """
    Run all correction stages and return (corrected_text, log).
    """
    log = {"original_length": len(text), "corrections": []}
    original = text

    # Stage A
    text = normalize_unicode(text)
    text = fix_combining_sequences(text)
    if text != original:
        log["corrections"].append("unicode_normalization")

    # Stage B
    validity = compute_word_validity(text)
    log["word_validity_ratio"] = round(validity, 4)

    # Stage C
    prev = text
    text = fix_matra_errors(text)
    text = fix_hasanta(text)
    text = fix_digit_consistency(text)
    if text != prev:
        log["corrections"].append("pattern_correction")

    # Stage D: Gemini validation for low-validity Bangla text
    bn_ratio = bangla_char_ratio(text)
    if bn_ratio > 0.2 and validity < 0.15 and len(text) > 30:
        text, was_corrected = validate_bangla_with_gemini(text)
        if was_corrected:
            log["corrections"].append("gemini_bangla_validation")
            # Recompute validity after correction
            new_validity = compute_word_validity(text)
            log["word_validity_after_gemini"] = round(new_validity, 4)

    log["corrected_length"] = len(text)
    log["edit_distance"] = _simple_edit_distance_ratio(original, text)

    return text, log


def _simple_edit_distance_ratio(a: str, b: str) -> float:
    """Quick ratio of character changes (not true Levenshtein)."""
    if not a and not b:
        return 0.0
    if a == b:
        return 0.0
    changes = sum(1 for ac, bc in zip(a, b) if ac != bc)
    changes += abs(len(a) - len(b))
    return round(changes / max(len(a), len(b)), 4)
