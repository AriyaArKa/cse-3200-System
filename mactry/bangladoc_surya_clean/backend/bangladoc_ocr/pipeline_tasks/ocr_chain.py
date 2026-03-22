"""OCR chain execution: Surya(optional) -> LLM chain -> EasyOCR.

SURYA_ENABLED from .env is the only control switch:
- true:  Surya -> Ollama -> Gemini -> EasyOCR
- false: Ollama -> Gemini -> EasyOCR
"""

from __future__ import annotations

from bangladoc_ocr import config
from bangladoc_ocr.core.ocr_engine import detections_to_blocks, run_dual_ocr
from bangladoc_ocr.core.surya_engine import is_available as surya_available
from bangladoc_ocr.core.surya_engine import ocr_bytes as surya_ocr
from bangladoc_ocr.fallback.llm_fallback import gemini_text_to_blocks, ocr_page_with_fallback
from bangladoc_ocr.models import ContentBlock
from bangladoc_ocr.nlp.confidence_scorer import score_blocks
from bangladoc_ocr.nlp.unicode_validator import is_wrong_script_for_bangla

from .helpers import apply_corrections, text_to_blocks


def _blocks_text(blocks: list[ContentBlock]) -> str:
    return "\n".join((b.text or "").strip() for b in blocks if (b.text or "").strip())


def _is_script_mismatch(blocks: list[ContentBlock]) -> bool:
    text = _blocks_text(blocks)
    return is_wrong_script_for_bangla(
        text,
        min_bangla_ratio=config.OCR_MIN_BANGLA_RATIO,
        devanagari_reject_threshold=config.OCR_DEVANAGARI_REJECT_THRESHOLD,
    )


def _try_surya(log: dict, img_bytes: bytes) -> tuple[list[ContentBlock], bool] | None:
    if not (config.SURYA_ENABLED and surya_available()):
        if config.SURYA_ENABLED:
            log["steps"].append("surya:unavailable")
        return None

    log["steps"].append("surya:trying")
    text = surya_ocr(img_bytes)
    if not text or len(text.strip()) < config.SURYA_MIN_TEXT_LEN:
        log["steps"].append("surya:empty_fallthrough")
        return None

    blocks = text_to_blocks(text)
    blocks, corrected = apply_corrections(blocks, source="surya")
    log["steps"].append(f"surya:ok:{len(text)}chars")
    return blocks, corrected


def _try_llm(log: dict, img_bytes: bytes, page_number: int) -> tuple[list[ContentBlock], str, bool] | None:
    log["steps"].append("llm_chain:trying")
    llm_text, llm_engine = ocr_page_with_fallback(img_bytes, page_number)
    if not llm_text or len(llm_text.strip()) < 20:
        log["steps"].append(f"llm_chain:failed:{llm_engine}")
        return None

    blocks = gemini_text_to_blocks(llm_text, page_number)
    blocks, corrected = apply_corrections(blocks, source="ollama")
    if _is_script_mismatch(blocks):
        log["steps"].append(f"llm_chain:script_mismatch:{llm_engine}")
        return None
    log["steps"].append(f"llm_chain:ok:{llm_engine}:{len(llm_text)}chars")
    return blocks, llm_engine, corrected


def _try_easyocr(log: dict, img_bytes: bytes) -> tuple[list[ContentBlock], bool]:
    log["steps"].append("easyocr:trying")
    detections = run_dual_ocr(img_bytes)
    blocks = detections_to_blocks(detections)
    blocks, corrected = apply_corrections(blocks, source="easyocr")
    if _is_script_mismatch(blocks):
        log["steps"].append("easyocr:script_mismatch")
    log["steps"].append(f"easyocr:{len(detections)}detections")
    return blocks, corrected


def run_scanned_ocr(
    img_bytes: bytes,
    page_number: int,
    log: dict,
) -> tuple[list[ContentBlock], str, str, bool]:
    mode = "surya_first" if config.SURYA_ENABLED else "skip_surya"
    log["steps"].append(f"ocr_mode:{mode}")

    if config.SURYA_ENABLED:
        surya_attempt = _try_surya(log, img_bytes)
        if surya_attempt:
            blocks, corrected = surya_attempt
            return blocks, "ocr_local", "surya", corrected
    else:
        log["steps"].append("surya:skipped_by_env")

    llm_attempt = _try_llm(log, img_bytes, page_number)
    if llm_attempt:
        blocks, llm_engine, corrected = llm_attempt
        return blocks, "ocr_api", llm_engine, corrected

    blocks, corrected = _try_easyocr(log, img_bytes)
    local_is_bangla = any(block.language in ("bn", "mixed") for block in blocks)
    local_confidence = score_blocks(blocks, local_is_bangla)
    log["steps"].append(f"easyocr:score:{local_confidence:.3f}")
    return blocks, "ocr_local", "easyocr", corrected
