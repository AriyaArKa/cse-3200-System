"""Main OCR processing pipeline with thread-based batching.

Routing for scanned pages:
  1. Ollama FIRST (if available) — best Bangla accuracy
  2. Validate response (hallucination check)
  3. If Ollama fails/hallucinates → retry at DPI_HIGH
  4. EasyOCR fallback (forms, English, when Ollama unavailable)

REMOVED: _estimate_bangla_ratio_quick() — was circular.
  EasyOCR fails on the crop → returns empty → ratio=0.0 → Ollama
  never called → EasyOCR used on full page → same Bangla failures.
"""

from __future__ import annotations

import gc
import hashlib
import io
import json
import logging
import re
import struct
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
from .fallback.llm_fallback import gemini_text_to_blocks
from .models import (
    ContentBlock,
    DocumentResult,
    ImageResult,
    PageExtraction,
    PageResult,
    TableResult,
)
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


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_page_decisions(page_num, page_log, method, engine):
    decisions = []
    for entry in page_log.get("ollama_decisions", []):
        decisions.append(entry)
    for step in page_log.get("steps", []):
        sev = "warning" if ("failed" in step or "error" in step) else "info"
        decisions.append({"page": page_num, "keyword": "PIPELINE_STEP",
                          "detail": step, "severity": sev})
    decisions.append({"page": page_num, "keyword": "FINAL_ENGINE",
                      "detail": f"method={method}, engine={engine}",
                      "severity": "info"})
    return decisions


def _generate_doc_id(pdf_path: str) -> str:
    stem = Path(pdf_path).stem
    return f"{stem}_{hashlib.md5(stem.encode()).hexdigest()[:8]}"


def _get_file_hash(pdf_path: str) -> str:
    h = hashlib.sha256()
    with open(pdf_path, "rb") as fh:
        h.update(fh.read(65536))
    return h.hexdigest()[:16]


_ollama_failed_this_session: bool = False


def _try_ollama_page(
    img_bytes: bytes,
    page_num: int,
    decisions: list,
) -> Optional[str]:
    """
    Attempt Ollama with full failure transparency.
    Returns result on success, None on any failure.
    Caller MUST check return value and log engine name accordingly.
    """
    global _ollama_failed_this_session

    from .fallback.llm_fallback import (
        _ocr_with_ollama,
        ensure_ollama_status,
        refine_ollama_ocr_text,
        _service_status,
    )

    if not config.OLLAMA_ENABLED or _ollama_failed_this_session:
        decisions.append({
            "page": page_num,
            "keyword": "OLLAMA_SKIPPED",
            "detail": "disabled or previous failure this session",
            "severity": "info",
        })
        return None

    ensure_ollama_status(force=False)

    if not _service_status.get("ollama_available"):
        decisions.append({
            "page": page_num,
            "keyword": "OLLAMA_SKIPPED",
            "detail": _service_status.get("ollama_error") or "ollama unavailable",
            "severity": "info",
        })
        return None

    model = _service_status.get("ollama_model") or ""
    if not model:
        decisions.append({
            "page": page_num,
            "keyword": "OLLAMA_SKIPPED",
            "detail": "no ollama model",
            "severity": "info",
        })
        return None

    t0 = time.time()
    try:
        text = _ocr_with_ollama(img_bytes, page_num, model)
        elapsed = time.time() - t0
        if text:
            refined = refine_ollama_ocr_text(text, model)
            if refined and refined != text:
                text = refined
                decisions.append({
                    "page": page_num,
                    "keyword": "OLLAMA_REFINED",
                    "detail": "text-only cleanup pass applied",
                    "severity": "info",
                })
            stat = config.get_status()
            model_name = stat.get("ollama_model") or model
            conf_proxy = min(1.0, len(text) / 5000.0)
            decisions.append({
                "page": page_num,
                "keyword": "OLLAMA_SUCCESS",
                "detail": (
                    f"model={model_name} elapsed={elapsed:.1f}s conf={conf_proxy:.3f}"
                ),
                "severity": "info",
            })
            return text

        decisions.append({
            "page": page_num,
            "keyword": "OLLAMA_FAILED",
            "detail": "empty or short response",
            "severity": "warning",
        })
        return None

    except Exception as exc:
        elapsed = time.time() - t0
        logger.warning(
            "Ollama FAILED page %d after %.1fs — %s: %s",
            page_num,
            elapsed,
            type(exc).__name__,
            str(exc)[:120],
        )
        decisions.append({
            "page": page_num,
            "keyword": "OLLAMA_FAILED",
            "detail": f"{type(exc).__name__}: {str(exc)[:100]}",
            "severity": "warning",
        })
        config.set_status("ollama_available", False)
        _service_status["ollama_available"] = False
        _ollama_failed_this_session = True
        return None


def _llm_ocr_image(img_bytes: bytes, page_num: int, page_log: dict) -> tuple[Optional[str], str]:
    """Try Ollama (with transparency), then Gemini. Updates page_log['ollama_decisions']."""
    ollama_pre: list = []
    api_text = _try_ollama_page(img_bytes, page_num, ollama_pre)
    page_log.setdefault("ollama_decisions", []).extend(ollama_pre)
    if api_text:
        model = config.get_status().get("ollama_model", "unknown")
        return api_text, f"ollama:{model}"
    from .fallback.llm_fallback import _ocr_with_gemini
    gemini_text = _ocr_with_gemini(img_bytes, page_num)
    if gemini_text:
        return gemini_text, "Gemini"
    return None, "None"


def _get_best_page_image(page: fitz.Page) -> bytes:
    """
    Use the raw embedded scan image when the page has exactly one large image.
    Upscale to min 1500px so qwen2.5vl can read small diacritics (matras).
    Fall back to DPI_HIGH render if no usable embedded image.
    """
    try:
        img_list = page.get_images(full=True)
        if len(img_list) == 1:
            doc = page.parent
            xref = img_list[0][0]
            base_image = doc.extract_image(xref)
            if base_image and base_image.get("width", 0) >= 600:
                raw = base_image["image"]
                from PIL import Image as PILImage
                pil = PILImage.open(io.BytesIO(raw))
                long_edge = max(pil.width, pil.height)
                if long_edge < 1500:
                    scale = 1500 / long_edge
                    pil = pil.resize(
                        (int(pil.width * scale), int(pil.height * scale)),
                        PILImage.LANCZOS,
                    )
                buf = io.BytesIO()
                pil.save(buf, format="PNG")
                return buf.getvalue()
    except Exception:
        pass
    return render_page_to_image(page, dpi=config.DPI_HIGH)


def _is_valid_ocr_response(text: str, img_bytes: bytes) -> tuple[bool, str]:
    """Detect hallucination: too few chars for the image pixel count."""
    text = (text or "").strip()
    if not text:
        return False, "empty response"

    char_count = len(text)
    img_pixels = 0
    try:
        if img_bytes[:4] == b"\x89PNG":
            w = struct.unpack(">I", img_bytes[16:20])[0]
            h = struct.unpack(">I", img_bytes[20:24])[0]
            img_pixels = w * h
        elif img_bytes[:2] == b"\xff\xd8":
            from PIL import Image as PILImage
            pil = PILImage.open(io.BytesIO(img_bytes))
            img_pixels = pil.width * pil.height
    except Exception:
        pass

    if img_pixels > 400_000 and char_count < 150:
        return False, f"hallucination: {char_count} chars for {img_pixels:,}px image"

    import re
    if img_pixels > 400_000 and not re.search(r"[০-৯0-9]", text) and char_count < 300:
        return False, f"suspicious: {char_count} chars, no digits"

    return True, "ok"


def _easyocr_output_is_noisy(blocks: list[ContentBlock]) -> tuple[bool, str]:
    """Heuristic guardrail for EasyOCR gibberish-heavy outputs on Bangla scans."""
    if not blocks:
        return True, "no blocks"

    total = len(blocks)
    low_conf = sum(1 for b in blocks if b.confidence < 0.35)
    single_char = sum(1 for b in blocks if len(b.text.strip()) <= 1)
    noisy_token = sum(
        1
        for b in blocks
        if re.search(r"[\[\]{}|`~^#@]", b.text or "")
        or bool(re.fullmatch(r"[^\u0980-\u09FFA-Za-z0-9]{2,}", (b.text or "").strip()))
    )

    if low_conf / total >= 0.25:
        return True, f"low_conf_ratio={low_conf/total:.2f}"
    if single_char / total >= 0.20:
        return True, f"single_char_ratio={single_char/total:.2f}"
    if noisy_token / total >= 0.12:
        return True, f"noise_token_ratio={noisy_token/total:.2f}"

    return False, "ok"


def _apply_corrections(blocks: list, page_log: dict, source: str = "easyocr") -> tuple:
    """Apply text correction pipeline. source='ollama' enables matra restoration."""
    correction_applied = False
    for block in blocks:
        if block.language in ("bn", "mixed"):
            block.text, corr_log = correct_bangla_text(block.text, source=source)
            if corr_log.get("corrections"):
                correction_applied = True
        block.text, num_disc = validate_and_fix_numbers(block.text)
        if num_disc:
            page_log.setdefault("numeric_fixes", []).extend(num_disc)
    return blocks, correction_applied


# ── Single-Page Processing ─────────────────────────────────────────────────

def _process_single_page(pdf_path, page_num, doc_id, domain="unknown"):
    page_log: dict = {"page_number": page_num, "steps": []}
    start = time.time()

    doc = open_pdf(pdf_path)
    page = doc[page_num - 1]
    dirs = ensure_output_dirs(doc_id)

    def _save_img(img_bytes: bytes) -> str:
        p = dirs["images"] / f"page_{page_num}.png"
        try:
            p.write_bytes(img_bytes)
            return str(p)
        except Exception:
            return ""

    source_image_path = ""
    page_type = detect_page_type(page)
    page_log["steps"].append(f"type_detection: {page_type}")

    content_blocks: list[ContentBlock] = []
    tables: list[TableResult] = []
    images: list[ImageResult] = []
    method, engine = "digital", "PyMuPDF"
    correction_applied = sent_to_api = False
    img_bytes: bytes = b""

    # ── DIGITAL PATH ───────────────────────────────────────────────────────
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

            for i, para in enumerate(
                p.strip() for p in raw_text.split("\n\n") if p.strip()
            ):
                b_ratio = bangla_char_ratio(para)
                lang = "bn" if b_ratio > 0.5 else ("mixed" if b_ratio > 0.1 else "en")
                content_blocks.append(
                    ContentBlock(block_id=i + 1, type="paragraph",
                                 language=lang, text=para, confidence=0.95)
                )

            tables = extract_tables_digital(pdf_path, page_num)
            for t in tables:
                t.rows, td = validate_table_numerics(t.rows)
                if td:
                    page_log.setdefault("table_numeric_fixes", []).extend(td)

        else:
            page_log["steps"].append("digital_rejected_corrupted_font")
            img_bytes = _get_best_page_image(page)
            source_image_path = _save_img(img_bytes)
            api_text, api_engine = _llm_ocr_image(img_bytes, page_num, page_log)
            if api_text:
                _v, _r = _is_valid_ocr_response(api_text, img_bytes)
                if _v:
                    content_blocks = gemini_text_to_blocks(api_text, page_num)
                    content_blocks, correction_applied = _apply_corrections(
                        content_blocks, page_log, source="ollama"
                    )
                    method, engine, sent_to_api = "ocr_api", api_engine, True
                    page_log["steps"].append(f"corrupted_font_llm_ok: {len(api_text)} chars")
                else:
                    page_log["steps"].append(f"corrupted_font_llm_bad: {_r}")
                    page_type = "scanned"
            else:
                page_type = "scanned"

    # ── SCANNED PATH ───────────────────────────────────────────────────────
    if page_type == "scanned":
        img_bytes = _get_best_page_image(page)
        source_image_path = _save_img(img_bytes)

        detections: list = []
        used_llm = False

        # ── LLM chain: Ollama (transparent) → Gemini → else EasyOCR ───────
        # Do NOT use EasyOCR crop to estimate Bangla ratio (circular failure).
        api_text, api_engine = _llm_ocr_image(img_bytes, page_num, page_log)

        if api_text:
            _v, _r = _is_valid_ocr_response(api_text, img_bytes)

            # Retry at DPI_HIGH if hallucination detected
            if not _v:
                page_log["steps"].append(f"ollama_rejected: {_r}")
                page_log["steps"].append("ollama_retry_dpi_high")
                img_hq = render_page_to_image(page, dpi=config.DPI_HIGH)
                api_text2, api_engine2 = _llm_ocr_image(img_hq, page_num, page_log)
                if api_text2:
                    _v2, _r2 = _is_valid_ocr_response(api_text2, img_hq)
                    if _v2:
                        api_text, api_engine = api_text2, api_engine2
                        img_bytes = img_hq
                        _v = True
                        page_log["steps"].append(
                            f"ollama_hq_success: {len(api_text)} chars"
                        )
                    else:
                        api_text = None
                        page_log["steps"].append(f"ollama_hq_bad: {_r2}")
                else:
                    api_text = None

            if api_text and _v:
                content_blocks = gemini_text_to_blocks(api_text, page_num)
                content_blocks, correction_applied = _apply_corrections(
                    content_blocks, page_log, source="ollama"
                )
                method, engine, sent_to_api, used_llm = (
                    "ocr_api", api_engine, True, True
                )
                page_log["steps"].append(
                    f"llm_ocr_success: {len(api_text)} chars, "
                    f"{len(content_blocks)} blocks"
                )
        else:
            page_log["steps"].append("llm_ocr_empty")

        # ── EasyOCR fallback ──────────────────────────────────────────────
        if not used_llm:
            page_log["steps"].append(
                "ollama_failed_using_easyocr"
                if page_log.get("ollama_decisions")
                else "ollama_unavailable_using_easyocr"
            )
            _easy_src = (
                "easyocr_fallback" if page_log.get("ollama_decisions") else "easyocr"
            )
            method, engine = "ocr_local", _easy_src

            img_ocr = render_page_to_image(page, dpi=config.DPI)
            detections = run_dual_ocr(img_ocr)
            page_log["steps"].append(f"easyocr: {len(detections)} detections")

            content_blocks = detections_to_blocks(detections)
            content_blocks, correction_applied = _apply_corrections(
                content_blocks, page_log, source=_easy_src
            )

            is_bn = any(b.language in ("bn", "mixed") for b in content_blocks)
            local_conf = score_blocks(content_blocks, is_bn)
            page_log["local_confidence"] = local_conf
            noisy_easyocr, noisy_reason = _easyocr_output_is_noisy(content_blocks)
            page_log["easyocr_noise_check"] = {
                "noisy": noisy_easyocr,
                "reason": noisy_reason,
            }

            # Secondary LLM attempt on low-confidence EasyOCR output
            should_secondary_llm = needs_api_fallback(local_conf, is_bn) or noisy_easyocr
            if should_secondary_llm:
                page_log["steps"].append("secondary_ollama_fallback")
                if noisy_easyocr:
                    page_log["steps"].append(f"easyocr_noisy: {noisy_reason}")
                api_text, api_engine = _llm_ocr_image(img_bytes, page_num, page_log)
                if api_text:
                    _v, _r = _is_valid_ocr_response(api_text, img_bytes)
                    if _v:
                        api_blocks = gemini_text_to_blocks(api_text, page_num)
                        if api_blocks:
                            api_blocks, _ = _apply_corrections(
                                api_blocks, page_log, source="ollama"
                            )
                            content_blocks = api_blocks
                            method, engine, sent_to_api = "ocr_api", api_engine, True
                            page_log["steps"].append("secondary_ollama_success")
                    else:
                        page_log["steps"].append(f"secondary_ollama_bad: {_r}")
                else:
                    # DPI escalation as last resort
                    if local_conf < 0.55:
                        img_hq = render_page_to_image(page, dpi=config.DPI_HIGH)
                        dets_hq = run_dual_ocr(img_hq)
                        if len(dets_hq) > len(detections):
                            content_blocks = detections_to_blocks(dets_hq)
                            content_blocks, _ = _apply_corrections(
                                content_blocks, page_log, source=_easy_src
                            )
                            page_log["steps"].append(
                                f"dpi_escalation: {len(dets_hq)} blocks"
                            )

        tables = extract_tables_scanned(img_bytes, detections, page_num)
        for t in tables:
            t.rows, td = validate_table_numerics(t.rows)
            if td:
                page_log.setdefault("table_numeric_fixes", []).extend(td)

    # ── Images ─────────────────────────────────────────────────────────────
    page_images_raw = extract_page_images(page)
    if page_images_raw:
        images = process_page_images(page_images_raw, page_num, dirs["images"])
        page_log["steps"].append(f"images_extracted: {len(images)}")

    doc.close()

    full_text = "\n".join(b.text for b in content_blocks)
    is_bangla_heavy = any(b.language in ("bn", "mixed") for b in content_blocks)
    final_confidence = score_blocks(content_blocks, is_bangla_heavy)

    # LLM confidence floor: prevents dictionary penalty from misrepresenting
    # correct Ollama output. Only applied when ≥30 words present (not hallucination).
    if method == "ocr_api" and is_bangla_heavy:
        _bn = bangla_char_ratio(full_text)
        _wc = len([w for w in full_text.split() if w.strip()])
        if _bn > 0.3 and _wc >= 30 and final_confidence < config.LLM_BANGLA_CONFIDENCE_FLOOR:
            final_confidence = config.LLM_BANGLA_CONFIDENCE_FLOOR
            page_log["steps"].append(f"llm_floor: {final_confidence:.2f}")

    page_log["processing_time_ms"] = round((time.time() - start) * 1000, 2)

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
        decisions=_build_page_decisions(page_num, page_log, method, engine),
    )


# ── Cache / Document helpers ───────────────────────────────────────────────

def _dict_to_document_result(raw: dict) -> DocumentResult:
    document = raw.get("document", {})
    summary = document.get("processing_summary", {})
    pages = []
    for p in raw.get("pages", []):
        ext = p.get("extraction", {})
        pages.append(PageResult(
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
        ))
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
    cache_path = config.MERGED_OUTPUT_DIR / f"_cache_{_get_file_hash(pdf_path)}.json"
    if cache_path.exists():
        logger.info("Cache hit: %s", Path(pdf_path).name)
        return _dict_to_document_result(
            json.loads(cache_path.read_text(encoding="utf-8"))
        )
    return None


def _save_cache(pdf_path: str, result: DocumentResult) -> None:
    cache_path = config.MERGED_OUTPUT_DIR / f"_cache_{_get_file_hash(pdf_path)}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(to_json_compatible(result.to_dict()), ensure_ascii=False, indent=2),
        encoding="utf-8",
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

    logger.info("Processing %s: %d pages", Path(pdf_path).name, total_pages)

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
                    page_results.append(PageResult(
                        page_number=pn,
                        extraction=PageExtraction(
                            method="error", engine="none",
                            confidence_score=0.0,
                            correction_applied=False,
                            numeric_validation_passed=False,
                        ),
                        content_blocks=[], tables=[], images=[],
                        full_text="", source_image_path="",
                        verified=False, domain=domain,
                        log={"error": str(exc)}, decisions=[],
                    ))
                finally:
                    pages_completed += 1
                    if progress_callback:
                        try:
                            progress_callback(pages_completed, total_pages)
                        except Exception:
                            pass
        gc.collect()

    page_results.sort(key=lambda p: p.page_number)

    all_languages: set[str] = set()
    has_tables = has_images = has_handwriting = False
    local_count = api_count = 0
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

    language_detected = sorted({
        "bn" if lang in ("bn", "mixed") else "en"
        for lang in all_languages if lang in ("bn", "mixed", "en")
    })

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