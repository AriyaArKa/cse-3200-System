"""
Bangla Corrector — Multi-stage correction for Bangla OCR text.

Stage A: Unicode normalization
Stage B: Dictionary validation (lightweight)
Stage C: Pattern-based correction (matra, hasanta, conjuncts)
Stage D: Gemini LLM validation (for very low-validity EasyOCR output)
Stage E: Matra restoration (Ollama output only — fixes stripped diacritics)
"""

import logging
import re
import unicodedata
from pathlib import Path
from typing import Tuple

from .. import config
from .unicode_validator import bangla_char_ratio

logger = logging.getLogger(__name__)

# ── Stage F: EasyOCR artifact cleanup (confirmed from real output analysis) ─
_PIPE_TO_DANDA = re.compile(r"\|(?=\s|$|\n)")
_BRACKET_DANDA = re.compile(r"(?<=[।\s\u0980-\u09FF])[\[\]](?=\s|$|\n)")
_BACKTICK_NOISE = re.compile(r"[`^~]{1,3}")
# Bengali year: ১০XX → ২০XX (digit ১ misread as ২ in year context)
_YEAR_FIX = re.compile(r"(?<!\d)১০([২-৯]\d)(?!\d)")
# ASCII digits inside Bengali Smarak numbers → Bengali
_ASCII_TO_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_SMARAK_RE = re.compile(r"(স্মারক\s*নং\s*[:।]?\s*)([\d০-৯.\s/]+)")

# Confirmed word-level confusions from real output files
# (notice_durga_puja, gazette, forwarding — all 7 Bangla scanned docs)
_EASYOCR_WORD_FIXES: dict[str, str] = {
    "বুলনা": "খুলনা",  # ব/খ visual confusion (notice_durga_puja)
    "নিজ্ঞপ্তি": "বিজ্ঞপ্তি",  # ন/ব confusion
    "নিজ্ঞপতি": "বিজ্ঞপ্তি",
    "অব্র": "অত্র",  # ব/ত confusion (notice_durga_puja)
    "প্রজ্ঞীপন": "প্রজ্ঞাপন",  # gazette vowel error
    "প্রজ্ঞাপণ": "প্রজ্ঞাপন",
    "মাচ ": "মার্চ ",  # month (gazette)
    "মার্ছ ": "মার্চ ",
    "বন্ খাকবে": "বন্ধ থাকবে",  # dropped hasanta (notice_durga_puja)
    "বন্ থাকবে": "বন্ধ থাকবে",
}


def fix_easyocr_artifacts(text: str) -> Tuple[str, bool]:
    """
    Stage F: Clean known EasyOCR artifact patterns.
    ONLY call when source == 'easyocr' or 'easyocr_fallback'.
    Confirmed against: notice_durga(0.66), gazette(0.72), forwarding(0.79),
    Image_001(0.74), Freedom_Fight(0.74) — all 7 Bangla scanned documents.
    """
    original = text

    text = _PIPE_TO_DANDA.sub("।", text)
    text = _BRACKET_DANDA.sub("।", text)
    text = _BACKTICK_NOISE.sub("", text)
    text = _YEAR_FIX.sub(lambda m: "২০" + m.group(1), text)

    # Smarak number: convert any ASCII digits to Bengali
    def _fix_smarak(m: re.Match) -> str:
        return m.group(1) + m.group(2).translate(_ASCII_TO_BN)

    text = _SMARAK_RE.sub(_fix_smarak, text)

    for wrong, right in _EASYOCR_WORD_FIXES.items():
        text = text.replace(wrong, right)

    return text, (text != original)


_BANGLA_CORRECTIONS = {
    "\u09be\u09be": "\u09be",  # double aa-kaar
    "\u09c7\u09c7": "\u09c7",  # double e-kaar
    "\u09cb\u09cb": "\u09cb",  # double o-kaar
}

_BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯"
_ASCII_DIGITS  = "0123456789"
_INVISIBLE_CHARS = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad]")
_BANGLA_COMBINING = set(range(0x09BE, 0x09CE)) | set(range(0x09D7, 0x09D8)) | {0x09CD}

# ── Stage A ────────────────────────────────────────────────────────────────

def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return _INVISIBLE_CHARS.sub("", text)


def fix_combining_sequences(text: str) -> str:
    result, prev_is_base = [], False
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("M"):
            if prev_is_base:
                result.append(ch)
        else:
            result.append(ch)
            prev_is_base = cat.startswith("L") or cat.startswith("N")
    return "".join(result)


# ── Stage B ────────────────────────────────────────────────────────────────

_FALLBACK_COMMON_BANGLA_WORDS = {
    "এবং","তার","এই","একটি","করা","হয়","থেকে","পর","সাথে","জন্য",
    "কিন্তু","যে","না","তা","আর","এক","দুই","তিন","বছর","সালে",
    "মধ্যে","পরে","দিন","কাজ","সময়","প্রতি","সকল","সব","মানুষ",
    "বাংলাদেশ","সরকার","শিক্ষা","বিশ্ববিদ্যালয়","বিভাগ","জেলা",
    "উপজেলা","প্রকল্প","কমিটি","সদস্য","সভাপতি","পরিচালক",
    "মন্ত্রণালয়","অফিস","নম্বর","তারিখ","বিষয়","অনুমোদন",
    "প্রেরক","প্রাপক","স্মারক","নং","শাখা","অনুচ্ছেদ","প্রধান",
    "মাধ্যমিক","উচ্চ","পরীক্ষা","ফলাফল","নিয়োগ","বেতন","ভাতা",
    "পদ","পদবি","জাতীয়","ক্রমিক",
}


def _load_common_bangla_words() -> set:
    wordlist_path = Path(__file__).resolve().parent.parent / "assets" / "bangla_wordlist.txt"
    try:
        if wordlist_path.exists():
            words = {
                line.strip() for line in wordlist_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            }
            if words:
                logger.info("Loaded %d Bangla words from %s", len(words), wordlist_path)
                return words
    except Exception as e:
        logger.warning("Failed to load Bangla wordlist: %s", e)
    return set(_FALLBACK_COMMON_BANGLA_WORDS)


_COMMON_BANGLA_WORDS = _load_common_bangla_words()


def compute_word_validity(text: str) -> float:
    words = text.split()
    bangla_words = [
        w for w in words
        if any(config.BANGLA_UNICODE_START <= ord(ch) <= config.BANGLA_UNICODE_END for ch in w)
    ]
    if not bangla_words:
        return 1.0
    known = sum(1 for w in bangla_words if w in _COMMON_BANGLA_WORDS)
    return known / len(bangla_words)


# ── Stage C ────────────────────────────────────────────────────────────────

def fix_matra_errors(text: str) -> str:
    for wrong, right in _BANGLA_CORRECTIONS.items():
        text = text.replace(wrong, right)
    text = re.sub(r"([\u09be-\u09cc])\1+", r"\1", text)
    return text


def fix_hasanta(text: str) -> str:
    text = text.replace("\u09cd\u09cd", "\u09cd")
    text = re.sub(r"(?<=\s)\u09CD", "", text)
    if text.startswith("\u09cd"):
        text = text[1:]
    return text


def fix_digit_consistency(text: str) -> str:
    if bangla_char_ratio(text) < 0.3:
        return text

    def _fix_token(match: re.Match) -> str:
        token = match.group(0)
        has_bn = any(ch in _BANGLA_DIGITS for ch in token)
        has_en = any(ch in _ASCII_DIGITS for ch in token)
        if has_bn and has_en:
            return "".join(
                _BANGLA_DIGITS[_ASCII_DIGITS.index(ch)] if ch in _ASCII_DIGITS else ch
                for ch in token
            )
        return token

    return re.sub(r"\S+", _fix_token, text)


# ── Stage D ────────────────────────────────────────────────────────────────

def validate_bangla_with_gemini(text: str) -> Tuple[str, bool]:
    if not config.GEMINI_API_KEY or len(text) < 20:
        return text, False
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = (
            "You are a Bangla language expert. Fix ONLY obvious OCR errors "
            "in the following Bangla text. Do NOT translate or add content. "
            "Return ONLY the corrected text.\n\n"
            "- Fix broken conjuncts (যুক্তবর্ণ)\n"
            "- Fix wrong matras (কার চিহ্ন)\n"
            "- Fix hasanta placement\n"
            "- Preserve all English text and numbers exactly\n\n"
            f"Text:\n{text[:2000]}"
        )
        response = client.models.generate_content(
            model=config.GEMINI_MODEL, contents=[prompt]
        )
        corrected = (response.text or "").strip()
        if corrected and len(corrected) > len(text) * 0.5:
            return corrected, corrected != text
        return text, False
    except Exception as e:
        logger.warning("Gemini Bangla validation failed: %s", e)
        return text, False


# ── Stage E: Ollama matra restoration ─────────────────────────────────────
# qwen2.5vl:7b at low resolution strips vowel diacritics (matras) from Bangla.
# This dictionary restores the most common stripped words.

_MATRA_RESTORATION = {
    # University / institution
    "বিশববিদযলয":   "বিশ্ববিদ্যালয়",
    "বিশববিদযলযের": "বিশ্ববিদ্যালয়ের",
    "বিশববিদযলযে":  "বিশ্ববিদ্যালয়ে",
    "পরকৌশল":       "প্রকৌশল",
    "পরযুকতি":      "প্রযুক্তি",
    "পরযুক্তি":     "প্রযুক্তি",
    "বিজঞপতি":      "বিজ্ঞপ্তি",
    "বিজঞপ্তি":     "বিজ্ঞপ্তি",
    # Place names
    "খুলন":         "খুলনা",
    "ঢাক":          "ঢাকা",
    "চটগরম":        "চট্টগ্রাম",
    # Formal / government
    "শিকষক":        "শিক্ষক",
    "শিকষরথী":      "শিক্ষার্থী",
    "শিকষরথ":       "শিক্ষার্থী",
    "করমকরত":       "কর্মকর্তা",
    "করমকরতর":      "কর্মকর্তার",
    "করমচর":        "কর্মচারী",
    "করমচরীর":      "কর্মচারীর",
    "নিরপতত":       "নিরাপত্তা",
    "নিরদেশ":       "নির্দেশ",
    "নিরদেশনম":     "নির্দেশনামে",
    "সমমনিত":       "সম্মানিত",
    "উপলকষে":       "উপলক্ষে",
    "করযলয":        "কার্যালয়",
    "করযকরম":       "কার্যক্রম",
    "মহোদযের":      "মহোদয়ের",
    "ভইস":          "ভাইস",
    "চযনসেলর":      "চ্যান্সেলর",
    "পরধন":         "প্রধান",
    "পরধনের":       "প্রধানের",
    "পরতিষঠন":      "প্রতিষ্ঠান",
    "পরতিষঠনের":    "প্রতিষ্ঠানের",
    "পরেরণ":        "প্রেরণ",
    "পরবিষট":       "প্রবিষ্ট",
    "সমরক":         "স্মারক",
    "সমরকনং":       "স্মারকনং",
    "তরিখ":         "তারিখ",
    "পরযনত":        "পর্যন্ত",
    "পরিচলক":       "পরিচালক",
    "বিভগীয":       "বিভাগীয়",
    "বিভগ":         "বিভাগ",
    "আঞচলিক":       "আঞ্চলিক",
    "সংরকষণ":       "সংরক্ষণ",
    "দপতর":         "দপ্তর",
    "শখ":           "শাখা",
    "যোগযোগ":       "যোগাযোগ",
    "ওযেবসইট":      "ওয়েবসাইট",
    "কমপিউটর":      "কম্পিউটার",
    "বোরড":         "বোর্ড",
    "গণপরজতনতরী":   "গণপ্রজাতন্ত্রী",
    "মনতরিপরিষদ":   "মন্ত্রিপরিষদ",
    "পরজঞপন":       "প্রজ্ঞাপন",
    "পদতযগ":        "পদত্যাগ",
    "পদতযগপতর":     "পদত্যাগপত্র",
    "রষটরপতি":      "রাষ্ট্রপতি",
    "মহমনয":        "মহামান্য",
    "পরবহণ":        "পরিবহণ",
    "শখখ":          "শাখা",
    "পররষটর":       "পররাষ্ট্র",
    "সচিবলয":       "সচিবালয়",
    "মনতরণলয":      "মন্ত্রণালয়",
}


def restore_stripped_matras(text: str) -> Tuple[str, bool]:
    """
    Fix words where Ollama stripped vowel diacritics (matras).
    Only applied to Ollama output (source='ollama').
    Returns (restored_text, was_changed).
    """
    words = text.split()
    result, changed = [], False
    for word in words:
        stripped = word.rstrip("।,?!;:()")
        suffix = word[len(stripped):]
        restored = _MATRA_RESTORATION.get(stripped)
        if restored:
            result.append(restored + suffix)
            changed = True
        else:
            result.append(word)
    return " ".join(result), changed


# ── Main pipeline ──────────────────────────────────────────────────────────

def correct_bangla_text(text: str, source: str = "easyocr") -> Tuple[str, dict]:
    """
    Run all correction stages. source='ollama' enables matra restoration.
    Returns (corrected_text, log_dict).
    """
    log = {"original_length": len(text), "corrections": [], "source": source}
    original = text

    # Stage A: Unicode normalization
    text = normalize_unicode(text)
    text = fix_combining_sequences(text)
    if text != original:
        log["corrections"].append("unicode_normalization")

    # Stage B: Word validity (informational)
    validity = compute_word_validity(text)
    log["word_validity_ratio"] = round(validity, 4)

    # Stage C: Pattern correction
    prev = text
    text = fix_matra_errors(text)
    text = fix_hasanta(text)
    text = fix_digit_consistency(text)
    if text != prev:
        log["corrections"].append("pattern_correction")

    # Stage D: Gemini correction (only for very low validity EasyOCR output)
    bn_ratio = bangla_char_ratio(text)
    if source == "easyocr" and bn_ratio > 0.2 and validity < 0.15 and len(text) > 30:
        text, was_corrected = validate_bangla_with_gemini(text)
        if was_corrected:
            log["corrections"].append("gemini_bangla_validation")
            log["word_validity_after_gemini"] = round(compute_word_validity(text), 4)

    # Stage E: Matra restoration (only for Ollama output)
    if source == "ollama":
        text, was_restored = restore_stripped_matras(text)
        if was_restored:
            log["corrections"].append("ollama_matra_restoration")

    # Stage F: EasyOCR artifact cleanup
    if source in ("easyocr", "easyocr_fallback", "EasyOCR_fallback"):
        text, was_fixed = fix_easyocr_artifacts(text)
        if was_fixed:
            log["corrections"].append("stage_f_easyocr_artifacts")
            log["stage_f_fixes"] = sum(
                1 for w in _EASYOCR_WORD_FIXES if w in original
            )

    log["corrected_length"] = len(text)
    log["edit_distance"] = _simple_edit_distance_ratio(original, text)
    return text, log


def _simple_edit_distance_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    if a == b:
        return 0.0
    changes = sum(1 for ac, bc in zip(a, b) if ac != bc) + abs(len(a) - len(b))
    return round(changes / max(len(a), len(b)), 4)