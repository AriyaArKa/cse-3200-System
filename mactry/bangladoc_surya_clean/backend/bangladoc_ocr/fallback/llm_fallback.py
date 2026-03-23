"""LLM fallback chain for OCR, composed from small task modules."""

from __future__ import annotations

from typing import List, Optional, Tuple

from bangladoc_ocr import config
from bangladoc_ocr.exceptions import LLMFallbackError
from bangladoc_ocr.models import ContentBlock

from .llm_tasks.gemini import ocr_with_gemini as _ocr_with_gemini
from .llm_tasks.ollama import ensure_ollama_status, ocr_with_ollama as _ocr_with_ollama_impl
from .llm_tasks.parser import text_to_blocks as _text_to_blocks
from .llm_tasks.prompts import load_prompts
from .llm_tasks.state import (
    get_api_stats_snapshot,
    get_service_status as _get_service_status_value,
    get_service_status_snapshot,
    increment_stat,
    set_stat,
)

_OCR_PROMPT, _OLLAMA_PROMPT = load_prompts()


def _ocr_with_ollama(img_bytes: bytes, page_number: int, model: str) -> Optional[str]:
    return _ocr_with_ollama_impl(img_bytes, page_number, model, _OLLAMA_PROMPT)


def _ocr_with_gemini_page(img_bytes: bytes, page_number: int) -> Optional[str]:
    return _ocr_with_gemini(img_bytes, page_number, _OCR_PROMPT)


def ocr_page_with_fallback(img_bytes: bytes, page_number: int) -> Tuple[Optional[str], str]:
    avail, model, ollama_err = ensure_ollama_status(force=False)

    if avail and model:
        text = _ocr_with_ollama(img_bytes, page_number, model)
        if text:
            set_stat("last_engine_used", "ollama")
            return text, f"ollama:{model}"
        ollama_err = _get_service_status_value("ollama_error") or "ollama_ocr_failed"
    else:
        ollama_err = ollama_err or "ollama_unavailable"

    text = _ocr_with_gemini_page(img_bytes, page_number)
    if text:
        set_stat("last_engine_used", "gemini")
        return text, "gemini"

    if not config.GEMINI_ENABLED:
        gemini_reason = "gemini_disabled"
    elif not config.GEMINI_API_KEY:
        gemini_reason = "gemini_missing_api_key"
    else:
        gemini_reason = "gemini_failed"

    increment_stat("errors")
    set_stat("last_engine_used", None)
    return None, f"none:ollama={ollama_err};gemini={gemini_reason}"


def ocr_with_llm_chain(img_bytes: bytes, page_number: int) -> str:
    text, _engine = ocr_page_with_fallback(img_bytes, page_number)
    if text:
        return text
    raise LLMFallbackError(f"All LLM engines failed on page {page_number}")


def gemini_text_to_blocks(text: str, page_number: int, offset: int = 1) -> List[ContentBlock]:
    del page_number
    return _text_to_blocks(text, offset=offset)


def get_service_status() -> dict:
    return get_service_status_snapshot()


def get_api_stats() -> dict:
    return get_api_stats_snapshot()
