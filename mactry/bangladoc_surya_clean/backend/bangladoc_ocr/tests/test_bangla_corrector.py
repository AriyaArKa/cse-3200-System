from bangladoc_ocr.nlp.bangla_corrector import (
    normalize_unicode, fix_combining_sequences,
    fix_matra_errors, fix_hasanta,
    correct_bangla_text, compute_word_validity,
)


def test_normalize_removes_zero_width():
    text = "বাংলা\u200b\u200cটেক্সট"
    result = normalize_unicode(text)
    assert "\u200b" not in result
    assert "\u200c" not in result


def test_fix_matra_errors_double_aa():
    assert "\u09be\u09be" not in fix_matra_errors("বা\u09be\u09beংলা")


def test_fix_hasanta_double():
    assert "\u09cd\u09cd" not in fix_hasanta("ক\u09cd\u09cdষ")


def test_word_validity_returns_float():
    score = compute_word_validity("বাংলাদেশ সরকার শিক্ষা বিভাগ")
    assert 0.0 <= score <= 1.0


def test_word_validity_known_beats_garbage():
    known = compute_word_validity("বাংলাদেশ সরকার শিক্ষা বিভাগ এবং জন্য")
    garb = compute_word_validity("ক্ষঞঢখঝঢ পখফগঘঙ ঝড়ঢ়বব")
    assert known >= garb


def test_correct_text_returns_tuple():
    result, log = correct_bangla_text("বাংলাদেশ সরকারের নির্দেশনা")
    assert isinstance(result, str) and "corrections" in log


def test_correct_text_preserves_english():
    result, _ = correct_bangla_text("বাংলা text এবং English mixed")
    assert "English" in result
    assert "text" in result
