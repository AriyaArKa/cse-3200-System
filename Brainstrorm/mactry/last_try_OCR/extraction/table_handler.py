"""Structured table extraction from digital and scanned PDFs."""

import logging
from typing import List

import pdfplumber

from ..models import TableResult

logger = logging.getLogger(__name__)


def extract_tables_digital(pdf_path: str, page_number: int) -> List[TableResult]:
    """
    Extract tables from a digital page using pdfplumber.
    page_number is 1-indexed.
    """
    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_number > len(pdf.pages):
                return tables
            page = pdf.pages[page_number - 1]
            raw_tables = page.extract_tables()
            for idx, raw_table in enumerate(raw_tables):
                if not raw_table:
                    continue
                # Clean cells: replace None with empty string
                rows = []
                for row in raw_table:
                    cleaned_row = [(cell.strip() if cell else "") for cell in row]
                    rows.append(cleaned_row)
                # Compute structure confidence based on consistency
                conf = _compute_table_confidence(rows)
                tables.append(
                    TableResult(
                        table_id=idx + 1,
                        structure_confidence=conf,
                        rows=rows,
                    )
                )
    except Exception as e:
        logger.error("pdfplumber table extraction failed page %d: %s", page_number, e)
    return tables


def extract_tables_scanned(
    img_bytes: bytes,
    ocr_detections: list,
    page_number: int,
) -> List[TableResult]:
    """
    Reconstruct table structure from OCR detections on a scanned page.
    Groups detections by rows based on vertical position.
    """
    if not ocr_detections:
        return []

    # Sort by Y coordinate (top of bbox)
    sorted_dets = sorted(
        ocr_detections,
        key=lambda d: d[2][0][1] if d[2] else 0,
    )

    # Group into rows by Y-proximity
    rows_raw = []
    current_row = [sorted_dets[0]]
    prev_y = sorted_dets[0][2][0][1] if sorted_dets[0][2] else 0

    for det in sorted_dets[1:]:
        y = det[2][0][1] if det[2] else 0
        if abs(y - prev_y) < 15:  # same row threshold
            current_row.append(det)
        else:
            rows_raw.append(current_row)
            current_row = [det]
            prev_y = y
    rows_raw.append(current_row)

    # Need at least 2 rows for a table
    if len(rows_raw) < 2:
        return []

    # Check if this looks like a table (consistent column count)
    col_counts = [len(r) for r in rows_raw]
    if len(set(col_counts)) > 3:  # too inconsistent
        return []

    # Sort each row by X coordinate and extract text
    rows = []
    for row in rows_raw:
        sorted_cells = sorted(
            row,
            key=lambda d: d[2][0][0] if d[2] else 0,
        )
        rows.append([d[0] for d in sorted_cells])

    conf = _compute_table_confidence(rows)
    return [
        TableResult(
            table_id=1,
            structure_confidence=conf,
            rows=rows,
        )
    ]


def _compute_table_confidence(rows: List[List[str]]) -> float:
    """
    Compute a confidence score for table structure based on:
    - Column count consistency
    - Non-empty cell ratio
    """
    if not rows:
        return 0.0

    col_counts = [len(r) for r in rows]
    mode_count = max(set(col_counts), key=col_counts.count)
    consistency = sum(1 for c in col_counts if c == mode_count) / len(col_counts)

    total_cells = sum(len(r) for r in rows)
    non_empty = sum(1 for r in rows for c in r if c.strip())
    fill_ratio = non_empty / total_cells if total_cells else 0.0

    return round(consistency * 0.6 + fill_ratio * 0.4, 4)
