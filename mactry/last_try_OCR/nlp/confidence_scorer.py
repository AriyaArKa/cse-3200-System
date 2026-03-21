"""
Confidence Scorer — language-aware multi-signal scoring.
Bangla and English are scored with different weight profiles because
government Bangla proper nouns devastate the dictionary signal.
"""

import logging
import re
from typing import List

from .. import config
from ..models import ContentBlock
from .bangla_corrector import compute_word_validity
from .unicode_validator import bangla_char_ratio, suspicious_glyph_count

logger = logging.getLogger(__name__)


def score_blocks(blocks: List[ContentBlock], is_bangla_heavy: bool) -> float:
    """
    Compute aggregate confidence using language-aware weighted scoring.
    Returns value in [0.0, 1.0].
    """
    if not blocks:
        return 0.0

    avg_ocr_conf = sum(b.confidence for b in blocks) / len(blocks)
    all_text = " ".join(b.text for b in blocks)
    bn_ratio = bangla_char_ratio(all_text)
    unicode_score = bn_ratio if is_bangla_heavy else (1.0 - bn_ratio)
    dict_score = compute_word_validity(all_text) if is_bangla_heavy else 0.8
    sus_count = suspicious_glyph_count(all_text)
    max_tolerable = max(len(all_text) * 0.02, 5)
    invalid_score = max(0.0, 1.0 - sus_count / max_tolerable)
    numeric_score = _numeric_consistency_score(all_text)
    struct_score = _structural_consistency(blocks)

    if is_bangla_heavy:
        score = (
            config.WEIGHT_OCR_CONFIDENCE_BN * avg_ocr_conf
            + config.WEIGHT_UNICODE_RATIO_BN * unicode_score
            + config.WEIGHT_DICTIONARY_MATCH_BN * dict_score
            + config.WEIGHT_INVALID_CHAR_BN * invalid_score
            + config.WEIGHT_REGEX_VALIDATION_BN * numeric_score
            + config.WEIGHT_STRUCTURAL_BN * struct_score
        )
    else:
        score = (
            config.WEIGHT_OCR_CONFIDENCE_EN * avg_ocr_conf
            + config.WEIGHT_UNICODE_RATIO_EN * unicode_score
            + config.WEIGHT_DICTIONARY_MATCH_EN * dict_score
            + config.WEIGHT_INVALID_CHAR_EN * invalid_score
            + config.WEIGHT_REGEX_VALIDATION_EN * numeric_score
            + config.WEIGHT_STRUCTURAL_EN * struct_score
        )

    return round(min(max(score, 0.0), 1.0), 4)


def needs_api_fallback(
    confidence: float,
    is_bangla_heavy: bool,
) -> bool:
    """
    Return True if this page should be sent to the LLM fallback chain.

    BUG FIX: was using BANGLA_MEDIUM_CONFIDENCE = 0.85, which triggered
    fallback on every single Bangla page. Now uses the correct variable
    API_FALLBACK_THRESHOLD_BANGLA = 0.62.
    """
    threshold = (
        config.API_FALLBACK_THRESHOLD_BANGLA
        if is_bangla_heavy
        else config.API_FALLBACK_THRESHOLD_ENGLISH
    )
    return confidence < threshold


def _numeric_consistency_score(text: str) -> float:
    patterns = re.findall(r"[OoIlSsBGZ]\d|\d[OoIlSsBGZ]", text)
    return max(0.0, 1.0 - len(patterns) * 0.05)


def _structural_consistency(blocks: List[ContentBlock]) -> float:
    if not blocks:
        return 0.0
    single_char = sum(1 for b in blocks if len(b.text.strip()) <= 1)
    return max(0.0, 1.0 - single_char / len(blocks))
