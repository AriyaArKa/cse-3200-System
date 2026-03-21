"""
Unicode Validator — Bangla-safe digital text validation.

Detects corrupted Bangla fonts, suspicious glyphs, and text
that should be re-processed via OCR instead of trusting the
embedded digital text.
"""

import logging
import math
import re
import unicodedata
from collections import Counter
from typing import Tuple

from .. import config

logger = logging.getLogger(__name__)

# CID reference pattern from pdfplumber (legacy font glyph IDs)
_CID_PATTERN = re.compile(r"\(cid:\d+\)")

# WinAnsi / SutonnyMJ legacy Bangla encoding artefact characters.
# These Latin/punctuation code-points are re-used as Bangla glyph slots in
# SutonnyMJ, BanglaWord, and similar legacy Windows fonts.
_WINANSA_ARTIFACTS = set("†‡÷©ÿÐ×ÞßðþæœŒ")


def _is_bangla_char(ch: str) -> bool:
    cp = ord(ch)
    return config.BANGLA_UNICODE_START <= cp <= config.BANGLA_UNICODE_END


def _is_ascii_letter(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def bangla_char_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Bangla."""
    if not text:
        return 0.0
    alpha = [ch for ch in text if ch.isalpha()]
    if not alpha:
        return 0.0
    bangla_count = sum(1 for ch in alpha if _is_bangla_char(ch))
    return bangla_count / len(alpha)


def suspicious_glyph_count(text: str) -> int:
    """Count characters that are known corrupt-font artifacts."""
    return sum(1 for ch in text if ch in config.SUSPICIOUS_GLYPHS)


def control_char_ratio(text: str) -> float:
    """Fraction of characters that are non-printable control chars (U+0001–U+001F
    excluding tab \\t, newline \\n, and carriage-return \\r).
    A high ratio is the strongest signal for SutonnyMJ / custom glyph encoding.
    """
    if not text:
        return 0.0
    ctrl = sum(1 for ch in text if 0 < ord(ch) < 32 and ch not in "\t\n\r")
    return ctrl / max(len(text), 1)


def winansa_artifact_count(text: str) -> int:
    """Count WinAnsi legacy Bangla font artefacts (†, ‡, ÷ etc.)."""
    return sum(1 for ch in text if ch in _WINANSA_ARTIFACTS)


def is_corrupted_font_text(text: str) -> bool:
    """Quick check: True if text appears to be from a legacy custom-encoded font."""
    ctrl_r = control_char_ratio(text)
    win_n = winansa_artifact_count(text)
    cid_n = len(_CID_PATTERN.findall(text))
    brk_d = bracket_density(text)
    sym_n = symbol_noise_ratio(text)
    bn_r = bangla_char_ratio(text)
    return (
        ctrl_r > 0.05
        or win_n >= 3
        or cid_n >= 3
        or brk_d > 0.05
        or (sym_n > 0.12 and bn_r < 0.05)
    )


def clean_text(text: str) -> str:
    """Remove control chars and CID references for human-readable/JSON output.

    Does NOT alter actual Bangla Unicode characters.
    """
    # Strip CID references like (cid:27)
    text = _CID_PATTERN.sub("", text)
    # Remove non-printable control chars (keep \t, \n, \r)
    text = "".join(ch if (ch >= " " or ch in "\t\n\r") else "" for ch in text)
    # Collapse runs of spaces and excessive blank lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ascii_dominance_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are ASCII."""
    if not text:
        return 0.0
    alpha = [ch for ch in text if ch.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for ch in alpha if _is_ascii_letter(ch)) / len(alpha)


# Characters that are legitimately common in real text (English or Bangla)
_COMMON_PUNCT = frozenset(".,!?;:'\"()-/_\\@#%&*+= ")


def bracket_density(text: str) -> float:
    """Fraction of characters that are bracket/brace chars heavily used by
    Bijoy and other legacy Bangla font encodings.

    In normal English prose this is well below 2%.  Bijoy-encoded Bangla text
    can exceed 8-15% because { } < > are used as glyph slots.
    """
    if not text:
        return 0.0
    brackets = sum(1 for ch in text if ch in "{}[]<>")
    return brackets / max(len(text), 1)


def symbol_noise_ratio(text: str) -> float:
    """Fraction of characters that are printable symbols NOT found in normal
    text (not letter, digit, whitespace, or common punctuation).

    A high ratio alongside zero Bangla Unicode chars is a strong signal for
    legacy font glyph-mapping (Bijoy, BijoyBaijra, etc.).
    """
    if not text:
        return 0.0
    noise = sum(
        1 for ch in text if not (ch.isalnum() or ch.isspace() or ch in _COMMON_PUNCT)
    )
    return noise / max(len(text), 1)


def entropy(text: str) -> float:
    """Shannon entropy of the character distribution."""
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)


def has_invalid_combining(text: str) -> bool:
    """Check for combining marks without a preceding base character."""
    prev_was_base = False
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("M"):  # Mark (combining)
            if not prev_was_base:
                return True
        prev_was_base = cat.startswith("L") or cat.startswith("N")
    return False


def validate_digital_text(text: str) -> Tuple[bool, dict]:
    """
    Validate extracted digital text for Bangla corruption.

    Returns (is_valid, report_dict).
    If is_valid is False, page should be re-routed to OCR.
    """
    report = {}

    # 1. Bangla ratio
    bn_ratio = bangla_char_ratio(text)
    report["bangla_char_ratio"] = round(bn_ratio, 4)

    # 2. Suspicious glyphs
    sus_count = suspicious_glyph_count(text)
    report["suspicious_glyph_count"] = sus_count

    # 3. ASCII dominance
    ascii_dom = ascii_dominance_ratio(text)
    report["ascii_dominance"] = round(ascii_dom, 4)

    # 4. Entropy
    ent = entropy(text)
    report["entropy"] = round(ent, 4)

    # 5. Invalid combining chars
    bad_combining = has_invalid_combining(text)
    report["invalid_combining"] = bad_combining

    # 6. Control character ratio (strongest signal for SutonnyMJ / PUA font encoding)
    ctrl_r = control_char_ratio(text)
    report["control_char_ratio"] = round(ctrl_r, 4)

    # 7. WinAnsi legacy Bangla font artefacts (†, ‡, ÷ …)
    win_n = winansa_artifact_count(text)
    report["winansa_artifact_count"] = win_n

    # 8. CID reference count — pdfplumber artefact from unmapped font glyphs
    cid_n = len(_CID_PATTERN.findall(text))
    report["cid_reference_count"] = cid_n

    # 9. Bracket density — Bijoy / BijoyBaijra encoding uses { } < > as glyph slots
    brk_d = bracket_density(text)
    report["bracket_density"] = round(brk_d, 4)

    # 10. Symbol noise ratio — printable but non-letter/digit/common-punct chars
    sym_n = symbol_noise_ratio(text)
    report["symbol_noise_ratio"] = round(sym_n, 4)

    # ── Decision logic ────────────────────────────────────────────────────────
    is_valid = True
    reasons = []

    # Control chars: the page text contains raw glyph-slot bytes (SutonnyMJ etc.)
    if ctrl_r > 0.05:
        is_valid = False
        reasons.append(f"High control-char ratio ({ctrl_r:.1%}): legacy font encoding")

    # WinAnsi Bangla artefacts
    if win_n >= 3:
        is_valid = False
        reasons.append(f"WinAnsi legacy Bangla font artefacts ({win_n} chars)")

    # CID references — completely unmapped font glyphs
    if cid_n >= 3:
        is_valid = False
        reasons.append(f"CID-mapped font glyphs ({cid_n} references)")

    # Bijoy / BijoyBaijra encoding: heavy use of { } < > as Bangla glyph slots
    if brk_d > 0.05:
        is_valid = False
        reasons.append(
            f"High bracket density ({brk_d:.1%}): Bijoy/BijoyBaijra legacy font encoding"
        )

    # General symbol noise with no real Bangla chars → corrupted encoding
    if sym_n > 0.12 and bn_ratio < 0.05:
        is_valid = False
        reasons.append(
            f"High symbol noise ({sym_n:.1%}) with no Bangla Unicode: corrupted encoding"
        )

    # Suspicious glyphs (existing check, lower threshold now that we have better detectors)
    if sus_count >= 5:
        is_valid = False
        reasons.append(f"High suspicious glyph count: {sus_count}")

    # English-only flag (only set when text genuinely looks like ASCII English)
    if (
        bn_ratio < 0.05
        and ascii_dom > 0.8
        and len(text) > 100
        and brk_d <= 0.05
        and sym_n <= 0.12
    ):
        report["possible_english_only"] = True

    # Very low entropy → garbled repetitive bytes
    if len(text) > 100 and ent < 2.0:
        is_valid = False
        reasons.append(f"Abnormally low entropy: {ent:.2f}")

    # Invalid combining char sequences
    if bad_combining:
        is_valid = False
        reasons.append("Invalid combining character sequences")

    report["is_valid"] = is_valid
    report["rejection_reasons"] = reasons

    if not is_valid:
        logger.warning("Digital text rejected: %s", "; ".join(reasons))

    return is_valid, report
