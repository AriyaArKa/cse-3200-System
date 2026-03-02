"""
Output Handler Module.
Handles saving results in both new and old (backward-compatible) JSON formats.

Old format:
{
  "pages": [
    {"source_file": "page_1.json", "data": {...}}
  ]
}
"""

import os
import json
import uuid
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from . import config
from .models import DocumentResult, PageResult

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames on Windows."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def save_page_json(
    page_result: PageResult,
    output_dir: Path,
    page_num: int,
    run_id: str,
) -> Path:
    """
    Save individual page result as JSON.
    Returns the path to the saved file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"page_{page_num}_{run_id}.json"
    output_path = output_dir / filename

    page_data = page_result.to_dict()
    output_path.write_text(
        json.dumps(page_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"Saved page JSON: {output_path}")
    return output_path


def save_merged_json(
    document_result: DocumentResult,
    output_dir: Path,
    pdf_name: str,
    run_id: str,
    use_old_format: bool = True,
) -> Path:
    """
    Save merged document JSON.
    If use_old_format=True, uses the backward-compatible format.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(Path(pdf_name).stem)
    filename = f"{safe_name}_{run_id}.json"
    output_path = output_dir / filename

    if use_old_format:
        data = document_result.to_old_format()
    else:
        data = document_result.to_dict()

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"Saved merged JSON: {output_path}")
    return output_path


def clean_json_text(text: str) -> str:
    """Strip markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def merge_page_jsons(json_files: List[str]) -> dict:
    """
    Merge individual page JSON files into one document.
    Compatible with old output format.
    """
    merged = {"pages": []}
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = clean_json_text(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = {"raw_text": cleaned}
        merged["pages"].append(
            {
                "source_file": os.path.basename(json_file),
                "data": data,
            }
        )
    return merged


def load_json_file(path: str) -> Optional[Dict]:
    """Load and parse a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = clean_json_text(raw)
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to load JSON: {path}: {e}")
        return None
