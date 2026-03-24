from last_try_OCR.nlp.unicode_validator import (
    bangla_char_ratio, suspicious_glyph_count,
    control_char_ratio, is_corrupted_font_text,
    validate_digital_text, clean_text,
)


def test_bangla_ratio_pure_bangla():
    assert bangla_char_ratio("বাংলাদেশ") > 0.9


def test_bangla_ratio_pure_english():
    assert bangla_char_ratio("Hello World") == 0.0


def test_bangla_ratio_mixed():
    ratio = bangla_char_ratio("বাংলা and English")
    assert 0.1 < ratio < 0.9


def test_control_char_ratio_clean():
    assert control_char_ratio("Normal text\nwith newlines") == 0.0


def test_control_char_ratio_corrupted():
    corrupted = "".join(chr(i) for i in range(1, 20))
    assert control_char_ratio(corrupted) > 0.5


def test_corrupted_font_clean_bangla():
    assert not is_corrupted_font_text("বাংলাদেশ সরকার একটি গণতান্ত্রিক রাষ্ট্র।")


def test_corrupted_font_legacy_chars():
    assert is_corrupted_font_text("†‡÷©ÿÐ×ÞßðþæœŒ†‡÷©")


def test_clean_text_removes_control_chars():
    assert "\x01" not in clean_text("Hello\x01\x02\x03World")


def test_clean_text_removes_cid():
    assert "(cid:" not in clean_text("Name: (cid:27)(cid:14)")


def test_validate_english_valid():
    is_valid, _ = validate_digital_text("This is a normal English document page.")
    assert is_valid


def test_validate_rejects_legacy_font():
    is_valid, report = validate_digital_text("†‡÷©ÿÐ×ÞßðþæœŒ" * 5)
    assert not is_valid
    assert report["rejection_reasons"]
