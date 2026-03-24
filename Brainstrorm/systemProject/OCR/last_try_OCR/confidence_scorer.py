"""
Confidence Scorer — Multi-signal confidence scoring for OCR output.
Determines whether a page needs API fallback.
"""

import logging
import re
from typing import List

from . import config
from .models import ContentBlock

logger = logging.getLogger(__name__)


def score_blocks(blocks: List[ContentBlock], is_bangla_heavy: bool) -> float:
    """
    Compute an aggregate confidence score for a list of content blocks.
    Uses weighted multi-signal scoring.
    """
    if not blocks:
        return 0.0

    # Signal 1: Average OCR confidence
    avg_ocr_conf = sum(b.confidence for b in blocks) / len(blocks)

    # Signal 2: Unicode ratio (Bangla validity)
    from .unicode_validator import bangla_char_ratio

    all_text = " ".join(b.text for b in blocks)
    bn_ratio = bangla_char_ratio(all_text)
    unicode_score = bn_ratio if is_bangla_heavy else (1.0 - bn_ratio)

    # Signal 3: Dictionary match
    from .bangla_corrector import compute_word_validity

    dict_score = compute_word_validity(all_text) if is_bangla_heavy else 0.8

    # Signal 4: Invalid character ratio
    from .unicode_validator import suspicious_glyph_count

    sus_count = suspicious_glyph_count(all_text)
    max_tolerable = max(len(all_text) * 0.02, 5)
    invalid_char_score = max(0.0, 1.0 - sus_count / max_tolerable)

    # Signal 5: Regex numeric validation
    numeric_score = _numeric_consistency_score(all_text)

    # Signal 6: Structural consistency
    structural_score = _structural_consistency(blocks)

    # Weighted aggregate
    score = (
        config.WEIGHT_OCR_CONFIDENCE * avg_ocr_conf
        + config.WEIGHT_UNICODE_RATIO * unicode_score
        + config.WEIGHT_DICTIONARY_MATCH * dict_score
        + config.WEIGHT_INVALID_CHAR * invalid_char_score
        + config.WEIGHT_REGEX_VALIDATION * numeric_score
        + config.WEIGHT_STRUCTURAL * structural_score
    )

    return round(min(max(score, 0.0), 1.0), 4)


def needs_api_fallback(
    confidence: float,
    is_bangla_heavy: bool,
) -> bool:
    """Determine if a page should be sent to Gemini API."""
    if is_bangla_heavy:
        return confidence < config.BANGLA_MEDIUM_CONFIDENCE
    return confidence < config.MEDIUM_CONFIDENCE


def _numeric_consistency_score(text: str) -> float:
    """Check for digit-confusion artifacts in text."""
    # Count suspicious patterns like O0, l1, S5 adjacency
    confusion_patterns = re.findall(r"[OoIlSsBGZ]\d|\d[OoIlSsBGZ]", text)
    if not confusion_patterns:
        return 1.0
    # Penalize based on frequency
    penalty = len(confusion_patterns) * 0.05
    return max(0.0, 1.0 - penalty)


def _structural_consistency(blocks: List[ContentBlock]) -> float:
    """
    Check if blocks have consistent structure:
    - Reasonable text lengths
    - Not too many single-char blocks
    """
    if not blocks:
        return 0.0
    single_char = sum(1 for b in blocks if len(b.text.strip()) <= 1)
    ratio = 1.0 - (single_char / len(blocks))
    return max(0.0, ratio)
