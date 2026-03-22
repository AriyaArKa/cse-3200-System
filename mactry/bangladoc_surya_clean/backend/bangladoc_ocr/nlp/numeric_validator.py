"""
Numeric Validator — Strict numeric preservation and validation.
Prevents digit substitution (0↔O, 1↔l, 5↔S) and validates
numeric consistency across OCR output.
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Common digit-confusion pairs
_CONFUSION_MAP = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "S": "5",
    "s": "5",
    "B": "8",
    "G": "6",
    "Z": "2",
}

# Regex to find numeric-like tokens (including with confusion chars)
_NUMERIC_PATTERN = re.compile(
    r"\b[\d" + re.escape("".join(_CONFUSION_MAP.keys())) + r"]+[.,\d]*\b"
)

# Pure numeric pattern
_PURE_NUMBER = re.compile(r"^[\d.,]+$")

# Bangla numerals
_BANGLA_NUMBER = re.compile(r"[০-৯]+")


def validate_and_fix_numbers(text: str) -> Tuple[str, List[dict]]:
    """
    Scan text for numeric tokens and fix digit-confusion errors.
    Returns (fixed_text, list_of_discrepancy_logs).
    Never changes pure Bangla numerals.
    """
    discrepancies = []

    def _fix_match(match: re.Match) -> str:
        token = match.group(0)

        # Skip pure Bangla numerals
        if _BANGLA_NUMBER.fullmatch(token):
            return token

        # Skip tokens that are already pure numbers
        if _PURE_NUMBER.fullmatch(token):
            return token

        # Check each char for confusion
        fixed_chars = []
        changed = False
        for ch in token:
            if ch in _CONFUSION_MAP and _looks_numeric_context(token):
                fixed_chars.append(_CONFUSION_MAP[ch])
                changed = True
            else:
                fixed_chars.append(ch)

        if changed:
            fixed = "".join(fixed_chars)
            discrepancies.append(
                {
                    "original": token,
                    "corrected": fixed,
                    "type": "digit_confusion",
                }
            )
            return fixed
        return token

    fixed_text = _NUMERIC_PATTERN.sub(_fix_match, text)
    return fixed_text, discrepancies


def _looks_numeric_context(token: str) -> bool:
    # Never fix inside email addresses or URLs
    if "@" in token or ("." in token and any(c.isalpha() for c in token)):
        return False
    digit_like = sum(
        1 for ch in token if ch.isdigit() or ch in _CONFUSION_MAP or ch in ".,"
    )
    return digit_like / max(len(token), 1) > 0.5


def validate_table_numerics(
    rows: List[List[str]],
) -> Tuple[List[List[str]], List[dict]]:
    """
    Validate and fix numeric values in table cells.
    Returns (fixed_rows, discrepancies).
    """
    all_discrepancies = []
    fixed_rows = []
    for row in rows:
        fixed_row = []
        for cell in row:
            fixed_cell, disc = validate_and_fix_numbers(cell)
            fixed_row.append(fixed_cell)
            all_discrepancies.extend(disc)
        fixed_rows.append(fixed_row)
    return fixed_rows, all_discrepancies
