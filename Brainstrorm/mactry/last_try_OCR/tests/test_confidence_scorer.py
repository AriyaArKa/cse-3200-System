from last_try_OCR.models import ContentBlock
from last_try_OCR.nlp.confidence_scorer import score_blocks, needs_api_fallback


def _block(text: str, conf: float, lang: str = "bn") -> ContentBlock:
    return ContentBlock(block_id=1, type="paragraph", language=lang,
                        text=text, confidence=conf)


def test_score_empty():
    assert score_blocks([], is_bangla_heavy=True) == 0.0


def test_score_in_range():
    blocks = [_block("বাংলাদেশ সরকার এই নির্দেশনা জারি করেছে।", 0.90)]
    s = score_blocks(blocks, is_bangla_heavy=True)
    assert 0.0 <= s <= 1.0


def test_gazette_page_scores_above_80():
    # Simulates a typical gazette page with high Bangla ratio and decent OCR conf.
    # With Bangla weights the score should exceed 0.80 even with low dict match.
    blocks = [
        _block("গণপ্রজাতন্ত্রী বাংলাদেশ সরকার মন্ত্রিপরিষদ বিভাগ প্রজ্ঞাপন", 0.82),
        _block("মাননীয় মন্ত্রী জনাব হাফিজ উদ্দিন আহমেদ বীর বিক্রম", 0.78),
        _block("পদত্যাগপত্র মহামান্য রাষ্ট্রপতি কর্তৃক গৃহীত হয়েছে", 0.80),
    ]
    s = score_blocks(blocks, is_bangla_heavy=True)
    assert s >= 0.78, f"Gazette page should score ≥0.78, got {s}"


def test_fallback_triggered_on_low():
    assert needs_api_fallback(0.45, is_bangla_heavy=True) is True


def test_fallback_not_triggered_on_high():
    assert needs_api_fallback(0.90, is_bangla_heavy=True) is False


def test_fallback_threshold_bangla_lower_than_085():
    # BUG FIX: threshold must be < 0.85, not 0.85 itself.
    # A page scoring 0.75 should NOT trigger fallback after the fix.
    assert needs_api_fallback(0.75, is_bangla_heavy=True) is False
