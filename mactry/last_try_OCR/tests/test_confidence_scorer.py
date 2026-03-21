import pytest

from last_try_OCR.models import ContentBlock
from last_try_OCR.nlp.confidence_scorer import needs_api_fallback, score_blocks


def _make_block(text: str, confidence: float) -> ContentBlock:
    return ContentBlock(
        block_id=1,
        type="paragraph",
        language="bn",
        text=text,
        confidence=confidence,
    )


def test_score_blocks_empty():
    assert score_blocks([], is_bangla_heavy=True) == 0.0


def test_score_blocks_high_confidence():
    blocks = [
        _make_block("বাংলাদেশ সরকার এই নির্দেশনা জারি করেছে।", 0.95),
        _make_block("শিক্ষা মন্ত্রণালয়ের অধীনে সকল প্রতিষ্ঠান।", 0.92),
    ]
    score = score_blocks(blocks, is_bangla_heavy=True)
    assert 0.0 <= score <= 1.0


def test_needs_api_fallback_low_confidence():
    assert needs_api_fallback(0.3, is_bangla_heavy=True) is True


def test_needs_api_fallback_high_confidence():
    assert needs_api_fallback(0.95, is_bangla_heavy=True) is False
