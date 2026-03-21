import pytest

from last_try_OCR.nlp.bangla_corrector import (
    compute_word_validity,
    correct_bangla_text,
    fix_combining_sequences,
    fix_hasanta,
    fix_matra_errors,
    normalize_unicode,
)


def test_normalize_unicode_removes_invisible():
    text = "বাংলা\u200b\u200cটেক্সট"
    result = normalize_unicode(text)
    assert "\u200b" not in result
    assert "\u200c" not in result


def test_fix_matra_errors_double_aa():
    text = "বাংলা\u09be\u09beদেশ"
    fixed = fix_matra_errors(text)
    assert "\u09be\u09be" not in fixed


def test_fix_hasanta_double():
    text = "বাংলা\u09cd\u09cdদেশ"
    fixed = fix_hasanta(text)
    assert "\u09cd\u09cd" not in fixed


def test_compute_word_validity_known_words():
    score_valid = compute_word_validity("বাংলাদেশ সরকার শিক্ষা বিভাগ")
    score_garbage = compute_word_validity("ক্ষঞঢখঝঢ পখফগঘঙ")
    assert score_valid >= score_garbage


def test_correct_bangla_text_returns_tuple():
    text = "বাংলাদেশ সরকারের নির্দেশনা"
    result, log = correct_bangla_text(text)
    assert isinstance(result, str)
    assert isinstance(log, dict)
    assert "corrections" in log


def test_correct_bangla_text_preserves_english():
    text = "বাংলা text এবং English mixed"
    result, _ = correct_bangla_text(text)
    assert "English" in result
    assert "text" in result
