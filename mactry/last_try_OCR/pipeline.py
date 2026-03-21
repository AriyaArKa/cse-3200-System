"""Main OCR processing pipeline with thread-based batching."""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import fitz

from . import config
from .core.ocr_engine import detections_to_blocks, run_dual_ocr
from .core.pdf_router import (
    detect_page_type,
    extract_digital_text,
    extract_page_images,
    open_pdf,
    render_page_to_image,
)
from .exceptions import LLMFallbackError
from .extraction.image_processor import process_page_images
from .extraction.table_handler import extract_tables_digital, extract_tables_scanned
from .fallback.llm_fallback import gemini_text_to_blocks, ocr_page_with_fallback
from .models import ContentBlock, DocumentResult, ImageResult, PageExtraction, PageResult, TableResult
from .nlp.bangla_corrector import (
    correct_bangla_text,
    fix_combining_sequences,
    normalize_unicode,
)
from .nlp.confidence_scorer import needs_api_fallback, score_blocks
from .nlp.numeric_validator import validate_and_fix_numbers, validate_table_numerics
from .nlp.unicode_validator import bangla_char_ratio, validate_digital_text
from .output.json_builder import ensure_output_dirs, save_document_json, to_json_compatible

logger = logging.getLogger(__name__)


def _build_page_decisions(page_num: int, page_log: dict, method: str, engine: str) -> list[dict]:
    """Convert internal page log steps into UI-facing decision entries."""
    decisions: list[dict] = []

    for step in page_log.get("steps", []):
        severity = "info"
        if "failed" in step or "error" in step:
            severity = "warning"
        decisions.append(
            {
                "page": page_num,
                "keyword": "PIPELINE_STEP",
                "detail": step,
                "severity": severity,
            }
        )

    decisions.append(
        {
            "page": page_num,
            "keyword": "FINAL_ENGINE",
            "detail": f"method={method}, engine={engine}",
            "severity": "info",
        }
    )
    return decisions


def _generate_doc_id(pdf_path: str) -> str:
    stem = Path(pdf_path).stem
    return f"{stem}_{hashlib.md5(stem.encode()).hexdigest()[:8]}"


def _get_file_hash(pdf_path: str) -> str:
    h = hashlib.sha256()
    with open(pdf_path, "rb") as fh:
        h.update(fh.read(65536))
    return h.hexdigest()[:16]


def _dict_to_document_result(raw: dict) -> DocumentResult:
    document = raw.get("document", {})
    summary = document.get("processing_summary", {})
    pages: list[PageResult] = []

    for p in raw.get("pages", []):
        ext = p.get("extraction", {})
        page = PageResult(
            page_number=int(p.get("page_number", 0)),
            extraction=PageExtraction(
                method=str(ext.get("method", "error")),
                engine=str(ext.get("engine", "none")),
                confidence_score=float(ext.get("confidence_score", 0.0)),
                correction_applied=bool(ext.get("correction_applied", False)),
                numeric_validation_passed=bool(ext.get("numeric_validation_passed", False)),
            ),
            content_blocks=[
                ContentBlock(
                    block_id=int(b.get("block_id", 0)),
                    type=str(b.get("type", "paragraph")),
                    language=str(b.get("language", "en")),
                    text=str(b.get("text", "")),
                    confidence=float(b.get("confidence", 0.0)),
                    is_handwritten=bool(b.get("is_handwritten", False)),
                )
                for b in p.get("content_blocks", [])
            ],
            tables=[
                TableResult(
                    table_id=int(t.get("table_id", 0)),
                    structure_confidence=float(t.get("structure_confidence", 0.0)),
                    rows=t.get("rows", []),
                )
                for t in p.get("tables", [])
            ],
            images=[
                ImageResult(
                    image_id=int(i.get("image_id", 0)),
                    type=str(i.get("type", "unknown")),
                    detected_text=str(i.get("detected_text", "")),
                    description=str(i.get("description", "")),
                    confidence=float(i.get("confidence", 0.0)),
                )
                for i in p.get("images", [])
            ],
            full_text=str(p.get("full_text", "")),
            source_image_path=str(p.get("source_image_path", "")),
            verified=bool(p.get("verified", False)),
            domain=str(p.get("domain", "unknown")),
            decisions=p.get("decisions", []),
        )
        pages.append(page)

    return DocumentResult(
        source=str(document.get("source", "")),
        total_pages=int(document.get("total_pages", 0)),
        language_detected=document.get("language_detected", []),
        has_handwriting=bool(document.get("has_handwriting", False)),
        has_tables=bool(document.get("has_tables", False)),
        has_images=bool(document.get("has_images", False)),
        pages_processed_locally=int(summary.get("pages_processed_locally", 0)),
        pages_sent_to_api=int(summary.get("pages_sent_to_api", 0)),
        overall_confidence=float(summary.get("overall_confidence", 0.0)),
        pages=pages,
        processing_time_ms=float(summary.get("processing_time_ms", 0.0)),
        document_decisions=document.get("all_decisions", []),
    )


def _load_cached(pdf_path: str) -> Optional[DocumentResult]:
    file_hash = _get_file_hash(pdf_path)
    cache_path = config.MERGED_OUTPUT_DIR / f"_cache_{file_hash}.json"
    if cache_path.exists():
        logger.info("Cache hit for %s (hash=%s)", Path(pdf_path).name, file_hash)
        return _dict_to_document_result(json.loads(cache_path.read_text(encoding="utf-8")))
    return None


def _save_cache(pdf_path: str, result: DocumentResult) -> None:
    file_hash = _get_file_hash(pdf_path)
    cache_path = config.MERGED_OUTPUT_DIR / f"_cache_{file_hash}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(to_json_compatible(result.to_dict()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _process_single_page(pdf_path: str, page_num: int, doc_id: str, domain: str = "unknown") -> PageResult:
    page_log: dict = {"page_number": page_num, "steps": []}
    start = time.time()

    doc = open_pdf(pdf_path)
    page = doc[page_num - 1]
    dirs = ensure_output_dirs(doc_id)

    def _persist_page_image(image_bytes: bytes) -> str:
        image_path = dirs["images"] / f"page_{page_num}.png"
        try:
            image_path.write_bytes(image_bytes)
            return str(image_path)
        except Exception as exc:
            logger.warning("Failed to save page render image %s: %s", image_path, exc)
            return ""

    source_image_path = ""
    page_type = detect_page_type(page)
    page_log["steps"].append(f"type_detection: {page_type}")

    content_blocks: list[ContentBlock] = []
    tables: list[TableResult] = []
    images: list[ImageResult] = []
    method = "digital"
    engine = "PyMuPDF"
    correction_applied = False
    sent_to_api = False

    if page_type == "digital":
        raw_text = extract_digital_text(page)
        page_log["steps"].append(f"digital_extraction: {len(raw_text)} chars")

        is_valid, val_report = validate_digital_text(raw_text)
        page_log["unicode_validation"] = val_report

        if is_valid:
            bn_ratio = bangla_char_ratio(raw_text)
            if bn_ratio > 0.3 and len(raw_text) > 50:
                raw_text = normalize_unicode(raw_text)
                raw_text = fix_combining_sequences(raw_text)
            elif bn_ratio > 0.1:
                raw_text, corr_log = correct_bangla_text(raw_text)
                correction_applied = bool(corr_log.get("corrections"))
                page_log["correction"] = corr_log

            raw_text, num_disc = validate_and_fix_numbers(raw_text)
            if num_disc:
                page_log["numeric_fixes"] = num_disc

            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                b_ratio = bangla_char_ratio(para)
                lang = "bn" if b_ratio > 0.5 else ("mixed" if b_ratio > 0.1 else "en")
                content_blocks.append(
                    ContentBlock(
                        block_id=i + 1,
                        type="paragraph",
                        language=lang,
                        text=para,
                        confidence=0.95,
                    )
                )

            tables = extract_tables_digital(pdf_path, page_num)
            for t in tables:
                t.rows, t_disc = validate_table_numerics(t.rows)
                if t_disc:
                    page_log.setdefault("table_numeric_fixes", []).extend(t_disc)
        else:
            page_log["steps"].append("digital_rejected_corrupted_font")
            img_bytes = render_page_to_image(page, dpi=config.DPI)
            source_image_path = _persist_page_image(img_bytes)
            api_text, api_engine = ocr_page_with_fallback(img_bytes, page_num)
            if api_text:
                content_blocks = gemini_text_to_blocks(api_text, page_num)
                for block in content_blocks:
                    if block.language in ("bn", "mixed"):
                        block.text, corr_log = correct_bangla_text(block.text)
                        if corr_log.get("corrections"):
                            correction_applied = True
                    block.text, num_disc = validate_and_fix_numbers(block.text)
                    if num_disc:
                        page_log.setdefault("numeric_fixes", []).extend(num_disc)
                method = "ocr_api"
                engine = api_engine
                sent_to_api = True
            else:
                page_type = "scanned"
                page_log["steps"].append("all_apis_direct_failed_falling_to_ocr")

    if page_type == "scanned":
        img_bytes = render_page_to_image(page, dpi=config.DPI)
        source_image_path = _persist_page_image(img_bytes)
        page_log["steps"].append(f"rendered_to_image (DPI={config.DPI})")

        method = "ocr_local"
        engine = "EasyOCR"
        detections = run_dual_ocr(img_bytes)
        page_log["steps"].append(f"easyocr: {len(detections)} detections")

        content_blocks = detections_to_blocks(detections)
        for block in content_blocks:
            if block.language in ("bn", "mixed"):
                block.text, corr_log = correct_bangla_text(block.text)
                if corr_log.get("corrections"):
                    correction_applied = True
            block.text, num_disc = validate_and_fix_numbers(block.text)
            if num_disc:
                page_log.setdefault("numeric_fixes", []).extend(num_disc)

        is_bangla_heavy = any(b.language in ("bn", "mixed") for b in content_blocks)
        confidence = score_blocks(content_blocks, is_bangla_heavy)
        page_log["local_confidence"] = confidence

        if needs_api_fallback(confidence, is_bangla_heavy):
            page_log["steps"].append("api_fallback_triggered")
            api_text, api_engine = ocr_page_with_fallback(img_bytes, page_num)
            if api_text:
                api_blocks = gemini_text_to_blocks(api_text, page_num)
                if api_blocks:
                    content_blocks = api_blocks
                    method = "ocr_api"
                    engine = api_engine
                    sent_to_api = True
                    page_log["steps"].append("api_fallback_success")
            else:
                page_log["steps"].append("api_fallback_failed_all_engines")

        tables = extract_tables_scanned(img_bytes, detections, page_num)
        for t in tables:
            t.rows, t_disc = validate_table_numerics(t.rows)
            if t_disc:
                page_log.setdefault("table_numeric_fixes", []).extend(t_disc)

    page_images_raw = extract_page_images(page)
    if page_images_raw:
        images = process_page_images(page_images_raw, page_num, dirs["images"])
        page_log["steps"].append(f"images_extracted: {len(images)}")

    doc.close()

    full_text = "\n".join(b.text for b in content_blocks)
    is_bangla_heavy = any(b.language in ("bn", "mixed") for b in content_blocks)
    final_confidence = score_blocks(content_blocks, is_bangla_heavy)

    page_log["processing_time_ms"] = round((time.time() - start) * 1000, 2)
    decisions = _build_page_decisions(page_num, page_log, method, engine)

    return PageResult(
        page_number=page_num,
        extraction=PageExtraction(
            method=method,
            engine=engine,
            confidence_score=final_confidence,
            correction_applied=correction_applied,
            numeric_validation_passed="numeric_fixes" not in page_log,
        ),
        content_blocks=content_blocks,
        tables=tables,
        images=images,
        full_text=full_text,
        source_image_path=source_image_path,
        verified=False,
        domain=domain,
        log=page_log,
        decisions=decisions,
    )


def process_pdf(
    pdf_path: str,
    use_multiprocessing: bool = True,
    domain: str = "unknown",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> DocumentResult:
    """Process an entire PDF into a DocumentResult."""
    start_time = time.time()
    pdf_path = str(Path(pdf_path).resolve())

    cached = _load_cached(pdf_path)
    if cached is not None:
        return cached

    doc_id = _generate_doc_id(pdf_path)
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    pages_completed = 0
    page_results: list[PageResult] = []
    page_ranges = [
        range(i, min(i + config.PAGE_BATCH_SIZE, total_pages + 1))
        for i in range(1, total_pages + 1, config.PAGE_BATCH_SIZE)
    ]

    for batch in page_ranges:
        workers = min(config.MAX_WORKERS, len(batch))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_single_page, pdf_path, pn, doc_id, domain): pn
                for pn in batch
            }
            for future in as_completed(futures):
                pn = futures[future]
                try:
                    page_results.append(future.result())
                except Exception as exc:
                    logger.error("Page %d failed: %s", pn, exc)
                    page_results.append(
                        PageResult(
                            page_number=pn,
                            extraction=PageExtraction(
                                method="error",
                                engine="none",
                                confidence_score=0.0,
                                correction_applied=False,
                                numeric_validation_passed=False,
                            ),
                            content_blocks=[],
                            tables=[],
                            images=[],
                            full_text="",
                            source_image_path="",
                            verified=False,
                            domain=domain,
                            log={"error": str(exc)},
                            decisions=[],
                        )
                    )
                finally:
                    pages_completed += 1
                    if progress_callback:
                        try:
                            progress_callback(pages_completed, total_pages)
                        except Exception:
                            pass
        gc.collect()

    page_results.sort(key=lambda p: p.page_number)

    all_languages = set()
    has_tables = False
    has_images = False
    has_handwriting = False
    local_count = 0
    api_count = 0
    confidence_sum = 0.0

    for page in page_results:
        for block in page.content_blocks:
            all_languages.add(block.language)
            if block.is_handwritten:
                has_handwriting = True
        has_tables = has_tables or bool(page.tables)
        has_images = has_images or bool(page.images)
        if page.extraction.method == "ocr_api":
            api_count += 1
        else:
            local_count += 1
        confidence_sum += page.extraction.confidence_score

    language_detected = sorted({"bn" if l in ("bn", "mixed") else "en" for l in all_languages if l in ("bn", "mixed", "en")})

    result = DocumentResult(
        source=Path(pdf_path).name,
        total_pages=total_pages,
        language_detected=language_detected,
        has_handwriting=has_handwriting,
        has_tables=has_tables,
        has_images=has_images,
        pages_processed_locally=local_count,
        pages_sent_to_api=api_count,
        overall_confidence=confidence_sum / max(total_pages, 1),
        pages=page_results,
        processing_time_ms=(time.time() - start_time) * 1000,
        document_decisions=[],
    )

    save_document_json(result, doc_id)
    _save_cache(pdf_path, result)
    return result
