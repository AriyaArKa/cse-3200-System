"""
JSON Builder — Assembles final structured JSON output and writes files.
Handles per-page JSON, merged document JSON, and output directory management.
"""

import json
import logging
from pathlib import Path
from typing import List

from . import config
from .models import DocumentResult, PageResult
from .unicode_validator import clean_text

logger = logging.getLogger(__name__)


def _sanitize(obj):
    """Recursively clean all string values in the result dict before writing JSON.

    Removes control characters (U+0001–U+001F) and CID references that arise
    from legacy font encodings (SutonnyMJ etc.).  Real Bangla Unicode chars
    (U+0980–U+09FF) are preserved unchanged.
    """
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        return [_sanitize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    return obj


def ensure_output_dirs(doc_id: str) -> dict:
    """Create output directories for a document and return paths."""
    dirs = {
        "images": config.OUTPUT_IMAGES_DIR / doc_id,
        "jsons": config.JSON_OUTPUT_DIR / doc_id,
        "merged": config.MERGED_OUTPUT_DIR,
        "logs": config.LOG_DIR,
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def save_page_json(page_result: PageResult, output_dir: Path):
    """Save a single page's result as JSON."""
    path = output_dir / f"page_{page_result.page_number}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_sanitize(page_result.to_dict()), f, ensure_ascii=False, indent=2)
    logger.info("Saved page JSON: %s", path)


def save_document_json(doc_result: DocumentResult, doc_id: str):
    """Save the merged document JSON."""
    dirs = ensure_output_dirs(doc_id)

    # Save per-page JSONs
    for page in doc_result.pages:
        save_page_json(page, dirs["jsons"])

    # Save merged document JSON
    merged_path = dirs["merged"] / f"{doc_id}.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(_sanitize(doc_result.to_dict()), f, ensure_ascii=False, indent=2)
    logger.info("Saved merged JSON: %s", merged_path)
    return merged_path


def load_document_json(doc_id: str) -> dict | None:
    """Load a previously saved document JSON."""
    path = config.MERGED_OUTPUT_DIR / f"{doc_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
