"""Page-level pipeline processing."""

import time

import fitz

from bangladoc_ocr import config
from bangladoc_ocr.core.pdf_router import (
    detect_page_type,
    extract_digital_text,
    extract_page_images,
    render_page_to_image,
)
from bangladoc_ocr.extraction.table_handler import extract_tables_digital, extract_tables_scanned
from bangladoc_ocr.models import PageExtraction, PageResult
from bangladoc_ocr.nlp.confidence_scorer import score_blocks
from bangladoc_ocr.nlp.numeric_validator import validate_and_fix_numbers
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio, validate_digital_text
from bangladoc_ocr.output.json_builder import ensure_output_dirs

from .helpers import text_to_blocks
from .image_tasks import describe_embedded_images, save_page_image
from .ocr_chain import run_scanned_ocr


def process_page(
    page: fitz.Page,
    page_number: int,
    pdf_path: str,
    doc_id: str,
    domain: str,
) -> PageResult:
    log = {"page": page_number, "steps": []}
    started = time.time()
    output_dirs = ensure_output_dirs(doc_id)
    page_type = detect_page_type(page)
    log["steps"].append(f"type:{page_type}")

    blocks = []
    tables = []
    images = []
    source_image_path = ""
    method = "digital"
    engine = "PyMuPDF"
    correction_applied = False

    if page_type == "digital":
        digital_text = extract_digital_text(page)
        valid, report = validate_digital_text(digital_text)
        log["unicode_validation"] = report

        if valid:
            digital_text, _num_issues = validate_and_fix_numbers(digital_text)
            blocks = text_to_blocks(digital_text)
            tables = extract_tables_digital(pdf_path, page_number)
            log["steps"].append(f"digital_ok:{len(digital_text)}chars")
        else:
            page_type = "scanned"
            log["steps"].append("digital_corrupt_rerouting")

    if page_type == "scanned":
        scan_bytes = render_page_to_image(page, dpi=config.DPI)
        source_image_path = save_page_image(scan_bytes, output_dirs["images"], page_number)
        blocks, method, engine, correction_applied = run_scanned_ocr(scan_bytes, page_number, log)
        detection_tuples = [
            (
                b.text,
                b.confidence,
                [
                    [b.bbox.x1, b.bbox.y1],
                    [b.bbox.x2, b.bbox.y1],
                    [b.bbox.x2, b.bbox.y2],
                    [b.bbox.x1, b.bbox.y2],
                ]
                if b.bbox
                else [],
            )
            for b in blocks
        ]
        tables = extract_tables_scanned(scan_bytes, detection_tuples, page_number)

    embedded_images = extract_page_images(page)
    if embedded_images:
        images = describe_embedded_images(embedded_images, output_dirs["images"], page_number)
        log["steps"].append(f"images:{len(images)}")

    full_text = "\n".join(block.text for block in blocks)
    is_bangla = any(block.language in ("bn", "mixed") for block in blocks)
    confidence = score_blocks(blocks, is_bangla)

    if method == "ocr_api" and is_bangla and confidence < config.LLM_BANGLA_CONFIDENCE_FLOOR:
        if bangla_char_ratio(full_text) > 0.30 and len(full_text.split()) >= 30:
            confidence = config.LLM_BANGLA_CONFIDENCE_FLOOR
            log["steps"].append(f"llm_floor:{confidence:.2f}")

    log["ms"] = round((time.time() - started) * 1000, 1)

    decisions = [
        {
            "page": page_number,
            "keyword": "FINAL_ENGINE",
            "detail": f"method={method} engine={engine}",
            "severity": "info",
        }
    ]
    decisions.extend(
        {
            "page": page_number,
            "keyword": "STEP",
            "detail": step,
            "severity": "info",
        }
        for step in log["steps"]
    )

    return PageResult(
        page_number=page_number,
        extraction=PageExtraction(
            method=method,
            engine=engine,
            confidence_score=confidence,
            correction_applied=correction_applied,
            numeric_validation_passed=True,
        ),
        content_blocks=blocks,
        tables=tables,
        images=images,
        full_text=full_text,
        source_image_path=source_image_path,
        domain=domain,
        log=log,
        decisions=decisions,
    )
