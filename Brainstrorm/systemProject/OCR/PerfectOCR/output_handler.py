"""
Output Handler Module for PerfectOCR.
Handles saving results as structured JSON files.
"""

import json
import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from . import config
from .models import DocumentResult, PageResult

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def save_page_json(
    page_data: Dict[str, Any],
    output_dir: Path,
    page_num: int,
    run_id: str,
) -> Path:
    """Save individual page result as JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"page_{page_num}_{run_id}.json"
    output_path = output_dir / filename

    output_path.write_text(
        json.dumps(page_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"Saved page JSON: {output_path}")
    return output_path


def save_document_json(
    document_result: DocumentResult,
    output_dir: Path,
    pdf_name: str,
    run_id: str,
) -> Path:
    """Save complete document result as JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(Path(pdf_name).stem)
    filename = f"{safe_name}_{run_id}.json"
    output_path = output_dir / filename

    output_path.write_text(
        document_result.to_json(),
        encoding="utf-8",
    )

    logger.info(f"Saved document JSON: {output_path}")
    return output_path
