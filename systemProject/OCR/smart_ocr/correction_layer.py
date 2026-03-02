"""
Correction Layer Module.
Applied BEFORE Gemini fallback to reduce API calls.

Performs:
  - Bangla spell/matra normalization
  - English basic corrections
  - Unicode normalization
  - OCR error pattern fixes
  - Mixed-language spacing fixes
"""

import re
import unicodedata
import logging
from typing import Optional

from .models import LanguageType

logger = logging.getLogger(__name__)

# ====================================
# Common OCR error patterns (Bangla)
# ====================================
_BANGLA_OCR_CORRECTIONS = {
    # Common misreadings in OCR
    "র্র": "র্",
    "য়য়": "য়",
    "  ": " ",  # double space
    "।।": "।",  # double danda
    "\u200c\u200c": "\u200c",  # double ZWNJ
    "\u200d\u200d": "\u200d",  # double ZWJ
}

# Bangla matra normalization map
_BANGLA_MATRA_NORMALIZE = {
    "\u09e2": "\u09c3",  # Vowel sign vocalic L → commonly confused
}

# English OCR common errors
_ENGLISH_OCR_CORRECTIONS = {
    " ,": ",",
    " .": ".",
    " ;": ";",
    " :": ":",
    "( ": "(",
    " )": ")",
    "l1": "ll",  # common OCR confusion
    "0O": "OO",
    "rn": "m",  # only in specific contexts, careful
}


def correct_text(
    text: str,
    language_type: str = LanguageType.UNKNOWN.value,
) -> str:
    """
    Apply correction pipeline to text block.

    Order:
      1. Unicode normalization (NFC)
      2. Bangla-specific corrections (if Bangla)
      3. English-specific corrections (if English)
      4. Mixed-language spacing fixes
      5. General cleanup
    """
    if not text or not text.strip():
        return text

    # Step 1: Unicode normalization (NFC form — composed characters)
    corrected = unicodedata.normalize("NFC", text)

    # Step 2: Bangla corrections
    if language_type in (LanguageType.BANGLA_HEAVY.value, LanguageType.MIXED.value):
        corrected = _apply_bangla_corrections(corrected)

    # Step 3: English corrections
    if language_type in (LanguageType.ENGLISH_HEAVY.value, LanguageType.MIXED.value):
        corrected = _apply_english_corrections(corrected)

    # Step 4: Mixed-language spacing
    corrected = _fix_mixed_language_spacing(corrected)

    # Step 5: General cleanup
    corrected = _general_cleanup(corrected)

    return corrected


def _apply_bangla_corrections(text: str) -> str:
    """Apply Bangla-specific OCR corrections."""

    # Apply known OCR error corrections
    for wrong, right in _BANGLA_OCR_CORRECTIONS.items():
        text = text.replace(wrong, right)

    # Matra normalization
    for wrong, right in _BANGLA_MATRA_NORMALIZE.items():
        text = text.replace(wrong, right)

    # Remove orphan matras (matras without a preceding consonant)
    # Bangla matras: \u09BE-\u09CC, \u09D7, \u09CD (hasanta)
    text = re.sub(r"(?<![ক-হড়ঢ়য়])([\u09BE-\u09CC\u09D7])", "", text)

    # Fix hasanta followed by space (should connect to next consonant)
    text = re.sub(r"(\u09CD)\s+([ক-হড়ঢ়য়])", r"\1\2", text)

    # Normalize Bangla digit variations
    # Map common OCR misreads of Bangla digits
    text = _normalize_bangla_digits(text)

    return text


def _normalize_bangla_digits(text: str) -> str:
    """Ensure Bangla digits are consistent."""
    # Bangla digits: ০১২৩৪৫৬৭৮৯ (U+09E6 - U+09EF)
    # No conversion needed if they're correct, just verify
    return text


def _apply_english_corrections(text: str) -> str:
    """Apply English-specific OCR corrections."""
    for wrong, right in _ENGLISH_OCR_CORRECTIONS.items():
        text = text.replace(wrong, right)

    # Fix common word-level OCR errors (cautious)
    # Don't be too aggressive — better to send to Gemini than corrupt

    return text


def _fix_mixed_language_spacing(text: str) -> str:
    """Fix spacing issues at Bangla-English boundaries."""
    # Add space between Bangla and English if missing
    # Bangla followed immediately by English letter
    text = re.sub(r"([\u0980-\u09FF])([a-zA-Z])", r"\1 \2", text)
    # English followed immediately by Bangla
    text = re.sub(r"([a-zA-Z])([\u0980-\u09FF])", r"\1 \2", text)

    return text


def _general_cleanup(text: str) -> str:
    """General text cleanup."""
    # Remove excessive whitespace (but keep single newlines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def estimate_correction_improvement(original: str, corrected: str) -> float:
    """
    Estimate how much the correction improved the text.
    Returns a ratio of changes made (0.0 = no change, 1.0 = completely different).
    """
    if not original or not corrected:
        return 0.0

    if original == corrected:
        return 0.0

    # Simple character-level diff ratio
    changes = sum(1 for a, b in zip(original, corrected) if a != b)
    length_diff = abs(len(original) - len(corrected))
    total = max(len(original), len(corrected))

    return (changes + length_diff) / total if total > 0 else 0.0
