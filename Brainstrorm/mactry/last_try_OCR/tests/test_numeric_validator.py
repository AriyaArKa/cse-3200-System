from last_try_OCR.nlp.numeric_validator import validate_and_fix_numbers, validate_table_numerics


def test_clean_numbers_unchanged():
    text = "Total: 1,234.56 units on 12/03/2026"
    fixed, disc = validate_and_fix_numbers(text)
    assert disc == []


def test_bangla_numerals_unchanged():
    text = "মোট: ১,২৩৪ টাকা তারিখ: ১২/০৩/২০২৬"
    fixed, disc = validate_and_fix_numbers(text)
    assert fixed == text
    assert disc == []


def test_table_empty():
    rows, disc = validate_table_numerics([])
    assert rows == []
    assert disc == []


def test_table_clean():
    rows = [["Name", "Amount"], ["Alice", "1000"], ["Bob", "2500"]]
    fixed, disc = validate_table_numerics(rows)
    assert fixed == rows
