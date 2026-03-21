import pytest

from last_try_OCR.nlp.unicode_validator import (
    bangla_char_ratio,
    clean_text,
    control_char_ratio,
    is_corrupted_font_text,
    suspicious_glyph_count,
    validate_digital_text,
)


def test_bangla_char_ratio_pure_bangla():
    assert bangla_char_ratio("বাংলাদেশ") > 0.9


def test_bangla_char_ratio_pure_english():
    assert bangla_char_ratio("Hello World") == 0.0


def test_bangla_char_ratio_mixed():
    ratio = bangla_char_ratio("বাংলা and English")
    assert 0.1 < ratio < 0.9


def test_control_char_ratio_clean():
    assert control_char_ratio("Normal text\nwith newlines") == 0.0


def test_control_char_ratio_corrupted():
    corrupted = "".join(chr(i) for i in range(1, 20))
    assert control_char_ratio(corrupted) > 0.5


def test_is_corrupted_font_text_clean_bangla():
    assert not is_corrupted_font_text("বাংলাদেশ সরকার একটি গণতান্ত্রিক রাষ্ট্র।")


def test_is_corrupted_font_text_legacy():
    assert is_corrupted_font_text("†‡÷©ÿÐ×ÞßðþæœŒ†‡÷©")


def test_clean_text_removes_control_chars():
    dirty = "Hello\x01\x02\x03World"
    assert clean_text(dirty) == "HelloWorld"


def test_clean_text_removes_cid():
    cid_text = "Name: (cid:27)(cid:14)(cid:8)"
    assert "(cid:" not in clean_text(cid_text)


def test_validate_digital_text_valid_english():
    is_valid, _ = validate_digital_text("This is a normal English document page.")
    assert is_valid


def test_validate_digital_text_rejects_corruption():
    is_valid, report = validate_digital_text("†‡÷©ÿÐ×ÞßðþæœŒ" * 5)
    assert not is_valid
    assert len(report["rejection_reasons"]) > 0
