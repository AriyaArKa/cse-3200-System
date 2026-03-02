"""
Shared utilities – config, logging, temp file management, text normalisation.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────── Configuration ──────────────────────────────

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
DPI: int = int(os.getenv("PDF_DPI", "300"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
TEMP_DIR: Path = Path(tempfile.gettempdir()) / "gemini_ocr"

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")

# ─────────────────────────────── Logging ──────────────────────────────────

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("gemini_ocr")

# ──────────────────────── Temp directory helpers ──────────────────────────


def create_temp_dir() -> Path:
    """Create and return a fresh temp directory for a single job."""
    job_dir = Path(tempfile.mkdtemp(dir=TEMP_DIR))
    return job_dir


def cleanup_temp_dir(path: Path) -> None:
    """Recursively remove a temp directory."""
    try:
        if path.exists():
            shutil.rmtree(path)
            logger.debug("Cleaned temp dir: %s", path)
    except Exception as exc:
        logger.warning("Failed to clean temp dir %s: %s", path, exc)


def ensure_base_temp_dir() -> None:
    """Make sure the base temp directory exists."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────── Text normalisation helpers ─────────────────────


_OCR_CHAR_MAP: dict[str, str] = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "S": "5",
    "B": "8",
}


def fix_ocr_number(text: str) -> str:
    """
    Attempt to fix common OCR digit‑substitution errors inside a string
    that is expected to be numeric (e.g. prices, quantities).
    Only applies when the string *looks* mostly numeric.
    """
    stripped = text.strip().replace(",", "").replace(" ", "")
    if not stripped:
        return text

    digit_ratio = sum(c.isdigit() or c == "." for c in stripped) / len(stripped)
    if digit_ratio < 0.5:
        return text  # not numeric enough – leave as‑is

    result: list[str] = []
    for ch in stripped:
        if ch in _OCR_CHAR_MAP and not ch.isdigit():
            result.append(_OCR_CHAR_MAP[ch])
        else:
            result.append(ch)
    return "".join(result)


# ────────────────────── Date normalisation (→ ISO 8601) ──────────────────

_DATE_PATTERNS: list[tuple[str, str]] = [
    # dd/mm/yyyy or dd-mm-yyyy
    (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", "%d/%m/%Y"),
    # mm/dd/yyyy
    (r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", "%m/%d/%Y"),
    # yyyy-mm-dd (already ISO but lets normalise separator)
    (r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", "%Y-%m-%d"),
    # Month dd, yyyy
    (r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", "%B %d %Y"),
    # dd Month yyyy
    (r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", "%d %B %Y"),
]


def normalise_date(text: str) -> str:
    """Best‑effort normalisation of a date string to ISO‑8601 (YYYY‑MM‑DD)."""
    text = text.strip()
    for pattern, fmt in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(0).replace("-", "/").replace(",", "")
            for alt_fmt in (fmt, fmt.replace("/", "-")):
                try:
                    dt = datetime.strptime(raw, alt_fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return text  # return original if nothing matched


def normalise_dates_in_dict(d: dict[str, str]) -> dict[str, str]:
    """Apply date normalisation to values whose keys look date‑related."""
    date_keys = {
        "date",
        "invoice_date",
        "due_date",
        "issue_date",
        "order_date",
        "payment_date",
        "ship_date",
        "delivery_date",
        "notice_date",
    }
    out: dict[str, str] = {}
    for k, v in d.items():
        if k.lower().replace(" ", "_") in date_keys:
            out[k] = normalise_date(v)
        else:
            out[k] = v
    return out
