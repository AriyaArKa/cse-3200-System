import pytest

from last_try_OCR.nlp.numeric_validator import validate_and_fix_numbers, validate_table_numerics


def test_no_change_for_clean_numbers():
    text = "Total: 1,234.56 units"
    fixed, disc = validate_and_fix_numbers(text)
    assert disc == []


def test_no_change_for_bangla_numerals():
    text = "মোট: ১,২৩৪ টাকা"
    fixed, disc = validate_and_fix_numbers(text)
    assert fixed == text
    assert disc == []


def test_table_numerics_empty():
    rows, disc = validate_table_numerics([])
    assert rows == []
    assert disc == []


def test_table_numerics_clean():
    rows = [["Name", "Amount"], ["Alice", "1000"], ["Bob", "2500"]]
    fixed_rows, disc = validate_table_numerics(rows)
    assert fixed_rows == rows
