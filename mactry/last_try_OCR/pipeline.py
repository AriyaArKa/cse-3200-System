"""
Pipeline — Main OCR processing pipeline with multiprocessing.
Orchestrates page routing, OCR, correction, validation, and output.
"""

import hashlib
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional

import fitz

from . import config
from .models import (
    ContentBlock,
    DocumentResult,
    ImageResult,
    PageExtraction,
    PageResult,
    TableResult,
)

logger = logging.getLogger(__name__)


def _generate_doc_id(pdf_path: str) -> str:
    """Generate a short unique ID from the filename."""
    name = Path(pdf_path).stem
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    return f"{name}_{h}"


# ── Decision Extraction ──────────────────────────────────────────────


def _extract_page_decisions(page_log: dict, page_num: int) -> list:
    """Convert raw page-processing log into human-readable decision entries.

    Each entry: { page, keyword, detail, severity }
    severity: 'info' | 'warning' | 'error'
    """
    decisions: list = []

    def _add(keyword: str, detail: str, severity: str = "info") -> None:
        decisions.append(
            {
                "page": page_num,
                "keyword": keyword,
                "detail": detail,
                "severity": severity,
            }
        )

    for step in page_log.get("steps", []):
        if step.startswith("type_detection:"):
            ptype = step.split(":", 1)[1].strip()
            _add(
                "DIGITAL" if ptype == "digital" else "SCANNED",
                f"Page classified as {ptype.upper()}",
            )
        elif step.startswith("digital_extraction:"):
            chars = step.split(":", 1)[1].strip()
            _add("TEXT_EXTRACTED", f"Digital text extracted ({chars})")
        elif step == "digital_rejected_falling_to_ocr":
            _add(
                "TEXT_REJECTED",
                "Digital text failed validation — routed to OCR",
                "warning",
            )
        elif step == "digital_rejected_corrupted_font":
            _add(
                "TEXT_REJECTED",
                "Corrupted font detected — sending directly to Gemini (skipping EasyOCR)",
                "warning",
            )
        elif step.startswith("rendered_for_gemini_direct"):
            _add("GEMINI_DIRECT", "Page rendered at low DPI for fast Gemini OCR")
        elif step == "gemini_direct_success":
            _add(
                "GEMINI_OK",
                "Gemini produced OCR output directly (EasyOCR skipped)",
            )
        elif step.startswith("ollama_direct_success"):
            engine = step.split(":", 1)[1].strip() if ":" in step else "Ollama"
            _add(
                "OLLAMA_OK",
                f"Gemini failed — {engine} produced OCR output directly (EasyOCR skipped)",
                "warning",
            )
        elif step == "all_apis_direct_failed_falling_to_ocr":
            _add(
                "ALL_API_FAILED",
                "Gemini + Ollama both failed — falling back to local OCR (EasyOCR)",
                "error",
            )
        elif step == "gemini_direct_failed_falling_to_ocr":
            _add(
                "GEMINI_FAILED",
                "Gemini direct OCR failed — falling back to EasyOCR",
                "error",
            )
        elif step.startswith("rendered_to_image"):
            _add("IMAGE_RENDER", f"Page rendered to image for OCR (DPI={config.DPI})")
        elif step.startswith("easyocr:"):
            n = step.split(":", 1)[1].strip()
            _add("EASYOCR", f"EasyOCR found {n}")
        elif step == "api_fallback_triggered":
            _add(
                "API_FALLBACK",
                "Low confidence — Gemini API fallback triggered",
                "warning",
            )
        elif step == "api_fallback_success":
            _add("GEMINI_OK", "Gemini API returned improved text")
        elif step.startswith("ollama_fallback_success"):
            engine = step.split(":", 1)[1].strip() if ":" in step else "Ollama"
            _add(
                "OLLAMA_OK",
                f"Gemini failed — {engine} returned improved text (final fallback)",
                "warning",
            )
        elif step == "api_fallback_failed_all_engines":
            _add(
                "ALL_API_FAILED",
                "Gemini + Ollama both failed — keeping local OCR result",
                "error",
            )
        elif step == "api_fallback_failed_keeping_local":
            _add("GEMINI_FAILED", "Gemini API failed — kept local OCR result", "error")
        elif step.startswith("images_extracted:"):
            n = step.split(":", 1)[1].strip()
            _add("IMAGES", f"Extracted {n}")
        elif step.startswith("final_engine:"):
            eng = step.split(":", 1)[1].strip()
            _add(
                "FINAL_ENGINE",
                f"Final output produced by: **{eng}**",
                "info" if eng == "PyMuPDF" else "warning",
            )
        elif step.startswith("final_method:"):
            meth = step.split(":", 1)[1].strip()
            _add("FINAL_METHOD", f"Extraction method: {meth}")

    # Unicode validation decisions
    val = page_log.get("unicode_validation", {})
    if val:
        for reason in val.get("rejection_reasons", []):
            _add("UNICODE_REJECT", reason, "warning")
        ctrl_r = val.get("control_char_ratio", 0) or 0
        if ctrl_r > 0.01:
            _add(
                "CTRL_CHARS",
                f"Control-char ratio: {ctrl_r:.1%}",
                "warning" if ctrl_r > 0.05 else "info",
            )
        cid_n = val.get("cid_reference_count", 0) or 0
        if cid_n:
            _add("CID_FONT", f"CID font references: {cid_n}", "warning")
        win_n = val.get("winansa_artifact_count", 0) or 0
        if win_n:
            _add("LEGACY_FONT", f"WinAnsi/SutonnyMJ artefacts: {win_n}", "warning")
        brk_d = val.get("bracket_density", 0) or 0
        if brk_d > 0.02:
            _add(
                "BIJOY_FONT",
                f"Bracket density: {brk_d:.1%} — Bijoy/BijoyBaijra encoding",
                "warning" if brk_d > 0.05 else "info",
            )
        sym_n = val.get("symbol_noise_ratio", 0) or 0
        if sym_n > 0.05:
            _add(
                "SYMBOL_NOISE",
                f"Symbol noise ratio: {sym_n:.1%}",
                "warning" if sym_n > 0.12 else "info",
            )

    # Bangla correction
    corr = page_log.get("correction", {})
    if corr:
        n_corr = len(corr.get("corrections", []))
        if n_corr:
            corr_types = ", ".join(corr.get("corrections", []))
            _add("BANGLA_CORRECTION", f"Applied {n_corr} correction(s): {corr_types}")
            if "gemini_bangla_validation" in corr.get("corrections", []):
                _add(
                    "GEMINI_BANGLA",
                    "Bangla text validated & corrected by Gemini LLM",
                )

    # Numeric fixes
    num_fixes = page_log.get("numeric_fixes", [])
    if num_fixes:
        _add("NUMERIC_FIX", f"Fixed {len(num_fixes)} numeric value(s)", "warning")

    # Table numeric fixes
    tbl_fixes = page_log.get("table_numeric_fixes", [])
    if tbl_fixes:
        _add(
            "TABLE_NUMERIC_FIX",
            f"Fixed {len(tbl_fixes)} table numeric value(s)",
            "warning",
        )

    # Local confidence score
    conf = page_log.get("local_confidence")
    if conf is not None:
        sev = "info" if conf >= 0.7 else "warning" if conf >= 0.4 else "error"
        _add("CONFIDENCE", f"Local OCR confidence: {conf:.1%}", sev)

    # Processing error
    err = page_log.get("error")
    if err:
        _add("PAGE_ERROR", str(err), "error")

    # Processing time
    proc_time = page_log.get("processing_time_ms")
    if proc_time is not None:
        _add("TIMING", f"Page processed in {proc_time:.0f}ms")

    return decisions


# ── Single-Page Processing (runs in worker) ──────────────────────────


def _process_single_page(
    pdf_path: str,
    page_num: int,  # 1-indexed
    doc_id: str,
    domain: str = "unknown",
) -> dict:
    """
    Process a single page end-to-end.
    Returns a serialisable dict (for multiprocessing compatibility).
    """
    # Re-import inside worker to avoid pickling issues
    from . import config
    from .pdf_router import (
        open_pdf,
        detect_page_type,
        extract_digital_text,
        render_page_to_image,
        extract_page_images,
    )
    from .unicode_validator import validate_digital_text, bangla_char_ratio
    from .ocr_engine import run_dual_ocr, detections_to_blocks
    from .bangla_corrector import correct_bangla_text
    from .numeric_validator import validate_and_fix_numbers, validate_table_numerics
    from .table_handler import extract_tables_digital, extract_tables_scanned
    from .image_processor import process_page_images
    from .confidence_scorer import score_blocks, needs_api_fallback
    from .api_fallback import ocr_page_with_fallback, gemini_text_to_blocks
    from .json_builder import ensure_output_dirs

    page_log = {"page_number": page_num, "steps": []}
    start = time.time()

    doc = open_pdf(pdf_path)
    page = doc[page_num - 1]

    dirs = ensure_output_dirs(doc_id)

    def _persist_page_image(image_bytes: bytes) -> str:
        """Persist OCR render image and return filesystem path string."""
        image_path = dirs["images"] / f"page_{page_num}.png"
        try:
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            return str(image_path)
        except Exception as e:
            logger.warning("Failed to save page render image %s: %s", image_path, e)
            return ""

    source_image_path = ""

    # ── Step 1: Page Type Detection ──────────────────────────────
    page_type = detect_page_type(page)
    page_log["steps"].append(f"type_detection: {page_type}")

    content_blocks: List[ContentBlock] = []
    tables: List[TableResult] = []
    images: List[ImageResult] = []
    method = "digital"
    engine = "PyMuPDF"
    correction_applied = False
    sent_to_api = False

    if page_type == "digital":
        # ── Step 2: Extract Digital Text ─────────────────────────
        raw_text = extract_digital_text(page)
        page_log["steps"].append(f"digital_extraction: {len(raw_text)} chars")

        # ── Step 3: Validate Unicode ─────────────────────────────
        is_valid, val_report = validate_digital_text(raw_text)
        page_log["unicode_validation"] = val_report

        if is_valid:
            # Use digital text — still run correction
            bn_ratio = bangla_char_ratio(raw_text)
            if bn_ratio > 0.1:
                raw_text, corr_log = correct_bangla_text(raw_text)
                correction_applied = bool(corr_log.get("corrections"))
                page_log["correction"] = corr_log

            # Fix numerics
            raw_text, num_disc = validate_and_fix_numbers(raw_text)
            if num_disc:
                page_log["numeric_fixes"] = num_disc

            # Build blocks from paragraphs
            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            for i, para in enumerate(paragraphs):
                bn_r = bangla_char_ratio(para)
                lang = "bn" if bn_r > 0.5 else ("mixed" if bn_r > 0.1 else "en")
                content_blocks.append(
                    ContentBlock(
                        block_id=i + 1,
                        type="paragraph",
                        language=lang,
                        text=para,
                        confidence=0.95,
                    )
                )

            # Tables from digital
            tables = extract_tables_digital(pdf_path, page_num)
            if tables:
                for t in tables:
                    t.rows, t_disc = validate_table_numerics(t.rows)
                    if t_disc:
                        page_log.setdefault("table_numeric_fixes", []).extend(t_disc)

        else:
            # Corrupted digital text — send DIRECTLY to Gemini (skip EasyOCR)
            page_log["steps"].append("digital_rejected_corrupted_font")
            img_bytes = render_page_to_image(page, dpi=config.DPI)
            page_log["steps"].append(f"rendered_for_gemini_direct (DPI={config.DPI})")
            source_image_path = _persist_page_image(img_bytes)

            api_text, api_engine = ocr_page_with_fallback(img_bytes, page_num)
            if api_text:
                content_blocks = gemini_text_to_blocks(api_text, page_num)
                # Apply correction to API output
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
                if api_engine.startswith("Ollama"):
                    page_log["steps"].append(f"ollama_direct_success:{api_engine}")
                else:
                    page_log["steps"].append("gemini_direct_success")
            else:
                # Gemini + Ollama both failed — fall back to local OCR
                page_type = "scanned"
                page_log["steps"].append("all_apis_direct_failed_falling_to_ocr")

            # Tables from corrupted digital — try digital first
            if content_blocks:
                tables = extract_tables_digital(pdf_path, page_num)
                if tables:
                    for t in tables:
                        t.rows, t_disc = validate_table_numerics(t.rows)
                        if t_disc:
                            page_log.setdefault("table_numeric_fixes", []).extend(
                                t_disc
                            )

    if page_type == "scanned":
        # ── Step 4: Render & OCR ─────────────────────────────────
        img_bytes = render_page_to_image(page, dpi=config.DPI)
        page_log["steps"].append(f"rendered_to_image (DPI={config.DPI})")
        source_image_path = _persist_page_image(img_bytes)

        method = "ocr_local"
        engine = "EasyOCR"

        detections = run_dual_ocr(img_bytes)
        page_log["steps"].append(f"easyocr: {len(detections)} detections")

        content_blocks = detections_to_blocks(detections)

        # Apply Bangla correction on each block
        for block in content_blocks:
            if block.language in ("bn", "mixed"):
                block.text, corr_log = correct_bangla_text(block.text)
                if corr_log.get("corrections"):
                    correction_applied = True

        # Fix numerics
        for block in content_blocks:
            block.text, num_disc = validate_and_fix_numbers(block.text)
            if num_disc:
                page_log.setdefault("numeric_fixes", []).extend(num_disc)

        # ── Step 5: Confidence Check & API Fallback ──────────────
        is_bangla_heavy = any(b.language in ("bn", "mixed") for b in content_blocks)
        confidence = score_blocks(content_blocks, is_bangla_heavy)
        page_log["local_confidence"] = confidence

        if needs_api_fallback(confidence, is_bangla_heavy):
            page_log["steps"].append("api_fallback_triggered")
            # Chain: Gemini → Ollama (final fallback)
            api_text, api_engine = ocr_page_with_fallback(img_bytes, page_num)
            if api_text:
                api_blocks = gemini_text_to_blocks(api_text, page_num)
                if api_blocks:
                    # Apply correction to API output too
                    for block in api_blocks:
                        if block.language in ("bn", "mixed"):
                            block.text, _ = correct_bangla_text(block.text)
                        block.text, _ = validate_and_fix_numbers(block.text)

                    content_blocks = api_blocks
                    method = "ocr_api"
                    engine = api_engine
                    sent_to_api = True
                    if api_engine.startswith("Ollama"):
                        page_log["steps"].append(
                            f"ollama_fallback_success:{api_engine}"
                        )
                    else:
                        page_log["steps"].append("api_fallback_success")
            else:
                # Both Gemini and Ollama failed — keep local OCR result
                page_log["steps"].append("api_fallback_failed_all_engines")

        # Tables from scanned
        tables = extract_tables_scanned(img_bytes, detections, page_num)
        if tables:
            for t in tables:
                t.rows, t_disc = validate_table_numerics(t.rows)
                if t_disc:
                    page_log.setdefault("table_numeric_fixes", []).extend(t_disc)

    # ── Step 6: Extract Images ───────────────────────────────────
    page_images_raw = extract_page_images(page)
    if page_images_raw:
        images = process_page_images(page_images_raw, page_num, dirs["images"])
        page_log["steps"].append(f"images_extracted: {len(images)}")

    doc.close()

    # ── Build Full Text ──────────────────────────────────────────
    full_text = "\n".join(b.text for b in content_blocks)

    # Final confidence
    is_bangla_heavy = any(b.language in ("bn", "mixed") for b in content_blocks)
    final_confidence = score_blocks(content_blocks, is_bangla_heavy)

    # Numeric validation pass check
    numeric_ok = "numeric_fixes" not in page_log

    page_log["processing_time_ms"] = round((time.time() - start) * 1000, 2)
    page_log["steps"].append(f"final_engine: {engine}")
    page_log["steps"].append(f"final_method: {method}")

    # Serialize for multiprocessing return
    return {
        "page_number": page_num,
        "extraction": {
            "method": method,
            "engine": engine,
            "confidence_score": final_confidence,
            "correction_applied": correction_applied,
            "numeric_validation_passed": numeric_ok,
        },
        "content_blocks": (
            [b.to_dict() for b in content_blocks] if content_blocks else []
        ),
        "tables": [t.to_dict() for t in tables],
        "images": [i.to_dict() for i in images],
        "full_text": full_text,
        "source_image_path": source_image_path,
        "verified": False,
        "domain": domain,
        "sent_to_api": sent_to_api,
        "log": page_log,
    }


# ── Document-Level Processing ────────────────────────────────────────


def process_pdf(
    pdf_path: str,
    use_multiprocessing: bool = True,
    domain: str = "unknown",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> DocumentResult:
    """
    Process an entire PDF document.
    Returns a fully structured DocumentResult.
    """
    start_time = time.time()
    pdf_path = str(Path(pdf_path).resolve())
    doc_id = _generate_doc_id(pdf_path)

    logger.info("Processing PDF: %s (doc_id=%s)", pdf_path, doc_id)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    logger.info("Total pages: %d", total_pages)

    # Process pages
    page_results_raw = []

    pages_completed = 0

    if use_multiprocessing and total_pages > 1:
        workers = min(config.MAX_WORKERS, total_pages)
        logger.info("Using %d workers for %d pages", workers, total_pages)

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_single_page,
                    pdf_path,
                    pn,
                    doc_id,
                    domain,
                ): pn
                for pn in range(1, total_pages + 1)
            }
            for future in as_completed(futures):
                pn = futures[future]
                try:
                    result = future.result()
                    page_results_raw.append(result)
                except Exception as e:
                    logger.error("Page %d failed: %s", pn, e)
                    page_results_raw.append(
                        {
                            "page_number": pn,
                            "extraction": {
                                "method": "error",
                                "engine": "none",
                                "confidence_score": 0.0,
                                "correction_applied": False,
                                "numeric_validation_passed": False,
                            },
                            "content_blocks": [],
                            "tables": [],
                            "images": [],
                            "full_text": "",
                            "sent_to_api": False,
                            "log": {"error": str(e)},
                        }
                    )
                finally:
                    pages_completed += 1
                    if progress_callback:
                        try:
                            progress_callback(pages_completed, total_pages)
                        except Exception:
                            pass
    else:
        for pn in range(1, total_pages + 1):
            try:
                result = _process_single_page(pdf_path, pn, doc_id, domain)
                page_results_raw.append(result)
            except Exception as e:
                logger.error("Page %d failed: %s", pn, e)
                page_results_raw.append(
                    {
                        "page_number": pn,
                        "extraction": {
                            "method": "error",
                            "engine": "none",
                            "confidence_score": 0.0,
                            "correction_applied": False,
                            "numeric_validation_passed": False,
                        },
                        "content_blocks": [],
                        "tables": [],
                        "images": [],
                        "full_text": "",
                        "sent_to_api": False,
                        "log": {"error": str(e)},
                    }
                )
            finally:
                pages_completed += 1
                if progress_callback:
                    try:
                        progress_callback(pages_completed, total_pages)
                    except Exception:
                        pass

    # Sort by page number
    page_results_raw.sort(key=lambda x: x["page_number"])

    # ── Assemble DocumentResult ──────────────────────────────────
    pages = []
    all_decisions: list = []
    all_languages = set()
    has_tables = False
    has_images = False
    has_handwriting = False
    local_count = 0
    api_count = 0
    confidence_sum = 0.0

    for pr in page_results_raw:
        ext = pr["extraction"]
        pg_decisions = _extract_page_decisions(pr.get("log", {}), pr["page_number"])
        all_decisions.extend(pg_decisions)
        page_result = PageResult(
            page_number=pr["page_number"],
            extraction=PageExtraction(
                method=ext["method"],
                engine=ext["engine"],
                confidence_score=ext["confidence_score"],
                correction_applied=ext["correction_applied"],
                numeric_validation_passed=ext["numeric_validation_passed"],
            ),
            content_blocks=[
                ContentBlock(
                    block_id=b["block_id"],
                    type=b["type"],
                    language=b["language"],
                    text=b["text"],
                    confidence=b["confidence"],
                    is_handwritten=b.get("is_handwritten", False),
                )
                for b in pr["content_blocks"]
            ],
            tables=[
                TableResult(
                    table_id=t["table_id"],
                    structure_confidence=t["structure_confidence"],
                    rows=t["rows"],
                )
                for t in pr["tables"]
            ],
            images=[
                ImageResult(
                    image_id=i["image_id"],
                    type=i["type"],
                    detected_text=i["detected_text"],
                    description=i["description"],
                    confidence=i["confidence"],
                )
                for i in pr["images"]
            ],
            full_text=pr["full_text"],
            source_image_path=pr.get("source_image_path", ""),
            verified=bool(pr.get("verified", False)),
            domain=pr.get("domain", domain),
            log=pr.get("log", {}),
            decisions=pg_decisions,
        )
        pages.append(page_result)

        # Aggregates
        for b in pr["content_blocks"]:
            all_languages.add(b["language"])
            if b.get("is_handwritten"):
                has_handwriting = True
        if pr["tables"]:
            has_tables = True
        if pr["images"]:
            has_images = True
        if pr["sent_to_api"]:
            api_count += 1
        else:
            local_count += 1
        confidence_sum += ext["confidence_score"]

    # Normalize languages
    lang_set = set()
    for l in all_languages:
        if l == "bn":
            lang_set.add("bn")
        elif l == "en":
            lang_set.add("en")
        elif l == "mixed":
            lang_set.add("bn")
            lang_set.add("en")

    elapsed = (time.time() - start_time) * 1000

    doc_result = DocumentResult(
        source=Path(pdf_path).name,
        total_pages=total_pages,
        language_detected=sorted(lang_set),
        has_handwriting=has_handwriting,
        has_tables=has_tables,
        has_images=has_images,
        pages_processed_locally=local_count,
        pages_sent_to_api=api_count,
        overall_confidence=confidence_sum / max(total_pages, 1),
        pages=pages,
        processing_time_ms=elapsed,
        document_decisions=all_decisions,
    )

    # Save outputs
    from .json_builder import save_document_json

    save_document_json(doc_result, doc_id)

    logger.info(
        "PDF processed: %d pages in %.1fs (local=%d, api=%d, conf=%.2f)",
        total_pages,
        elapsed / 1000,
        local_count,
        api_count,
        doc_result.overall_confidence,
    )

    return doc_result
