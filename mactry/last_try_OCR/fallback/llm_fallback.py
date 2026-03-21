"""LLM fallback chain: Gemini (optional) and Ollama (local)."""

from __future__ import annotations

import base64
import io
import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from .. import config
from ..exceptions import LLMFallbackError
from ..models import ContentBlock
from ..nlp.unicode_validator import bangla_char_ratio

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "prompts" / "ocr_prompt.txt"
)
_OLLAMA_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "prompts" / "ollama_prompt.txt"
)
_OCR_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else "Extract all text from this document image."
_OLLAMA_PROMPT: str = _OLLAMA_PROMPT_PATH.read_text(encoding="utf-8") if _OLLAMA_PROMPT_PATH.exists() else _OCR_PROMPT

_api_stats = {
    "gemini_calls": 0,
    "gemini_tokens": 0,
    "gemini_errors": 0,
    "ollama_calls": 0,
    "ollama_errors": 0,
    "total_calls": 0,
    "total_tokens": 0,
    "errors": 0,
    "last_engine_used": None,
}

_service_status = {
    "gemini_available": None,
    "gemini_error": None,
    "ollama_available": None,
    "ollama_model": None,
    "ollama_error": None,
}


def get_api_stats() -> dict:
    return dict(_api_stats)


def get_service_status() -> dict:
    return dict(_service_status)


def reset_api_stats() -> None:
    for key in _api_stats:
        _api_stats[key] = 0


def _check_ollama_available() -> Tuple[bool, Optional[str], Optional[str]]:
    if not config.OLLAMA_ENABLED:
        return False, None, "Ollama disabled in config"

    vision_keys = (
        "llava",
        "bakllava",
        "moondream",
        "minicpm",
        "qwen",
        "llama3.2-vision",
    )

    try:
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, None, f"Ollama API returned {resp.status_code}"

        available_models = [m["name"] for m in resp.json().get("models", [])]
        if not available_models:
            return False, None, "No models installed in Ollama"

        for model in config.OLLAMA_MODEL_PRIORITY:
            for avail in available_models:
                if model == avail or avail.startswith(model.split(":")[0]):
                    base = avail.split(":")[0].lower()
                    if any(k in base for k in vision_keys):
                        return True, avail, None

        for avail in available_models:
            base = avail.split(":")[0].lower()
            if any(k in base for k in vision_keys):
                return True, avail, None

        return False, None, "No vision model found"
    except requests.exceptions.ConnectionError:
        return False, None, "Cannot connect to Ollama"
    except Exception as exc:
        return False, None, str(exc)


def _ocr_with_ollama(img_bytes: bytes, page_number: int, model: str) -> Optional[str]:
    try:
        from PIL import Image as PILImage

        pil_img = PILImage.open(io.BytesIO(img_bytes))
        max_side = 1024
        if max(pil_img.size) > max_side:
            pil_img.thumbnail((max_side, max_side), PILImage.LANCZOS)

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        is_qwen = "qwen" in model.lower()
        if is_qwen:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": _OLLAMA_PROMPT,
                        "images": [img_b64],
                    }
                ],
                "stream": False,
                "options": {
                    "num_predict": 1024,
                    "num_ctx": 2048,
                    "temperature": 0.05,
                },
            }
            endpoint = f"{config.OLLAMA_BASE_URL}/api/chat"
        else:
            payload = {
                "model": model,
                "prompt": _OLLAMA_PROMPT,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "num_predict": 1024,
                    "num_ctx": 2048,
                    "temperature": 0.05,
                },
            }
            endpoint = f"{config.OLLAMA_BASE_URL}/api/generate"

        resp = requests.post(endpoint, json=payload, timeout=config.OLLAMA_TIMEOUT)
        if resp.status_code != 200:
            _api_stats["ollama_errors"] += 1
            return None

        result = resp.json()
        text = (
            (result.get("message", {}).get("content") or "").strip()
            if is_qwen
            else (result.get("response") or "").strip()
        )
        if text:
            _api_stats["ollama_calls"] += 1
            _api_stats["total_calls"] += 1
            logger.info("Ollama OCR page %s: %d chars", page_number, len(text))
            return text
        return None
    except Exception as exc:
        logger.warning("Ollama OCR failed: %s", exc)
        _api_stats["ollama_errors"] += 1
        return None


def _ocr_with_gemini(img_bytes: bytes, page_number: int) -> Optional[str]:
    if not config.GEMINI_API_KEY or not config.GEMINI_ENABLED:
        return None

    try:
        from google import genai
        from PIL import Image

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = Image.open(io.BytesIO(img_bytes))
        if max(image.size) > config.MAX_IMAGE_DIMENSION:
            image.thumbnail((config.MAX_IMAGE_DIMENSION, config.MAX_IMAGE_DIMENSION), Image.LANCZOS)

        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[_OCR_PROMPT, image],
                )
                _api_stats["gemini_calls"] += 1
                _api_stats["total_calls"] += 1

                if hasattr(response, "usage_metadata"):
                    tokens = getattr(response.usage_metadata, "total_token_count", 0)
                    _api_stats["gemini_tokens"] += tokens
                    _api_stats["total_tokens"] += tokens

                text = (response.text or "").strip()
                if text:
                    logger.info("Gemini OCR page %s: %d chars", page_number, len(text))
                    return text
            except Exception as exc:
                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    time.sleep(config.GEMINI_RETRY_DELAY)
                else:
                    logger.warning("Gemini OCR failed: %s", exc)

        _api_stats["gemini_errors"] += 1
        return None
    except Exception as exc:
        logger.warning("Gemini OCR unavailable: %s", exc)
        _api_stats["gemini_errors"] += 1
        return None


def ocr_with_llm_chain(img_bytes: bytes, page_number: int) -> str:
    """Try Gemini first (if enabled), then Ollama, otherwise raise."""
    text = _ocr_with_gemini(img_bytes, page_number)
    if text:
        _api_stats["last_engine_used"] = "gemini"
        return text

    if _service_status.get("ollama_available") is None:
        avail, model, err = _check_ollama_available()
        _service_status["ollama_available"] = avail
        _service_status["ollama_model"] = model
        _service_status["ollama_error"] = err
        config.set_status("ollama_available", avail)
        config.set_status("ollama_model", model)

    model = _service_status.get("ollama_model")
    if _service_status.get("ollama_available") and model:
        text = _ocr_with_ollama(img_bytes, page_number, model)
        if text:
            _api_stats["last_engine_used"] = "ollama"
            return text

    _api_stats["errors"] += 1
    _api_stats["last_engine_used"] = None
    raise LLMFallbackError(f"All LLM fallback engines failed on page {page_number}")


def ocr_page_with_fallback(img_bytes: bytes, page_number: int) -> Tuple[Optional[str], str]:
    """Compatibility wrapper returning (text, engine)."""
    try:
        text = ocr_with_llm_chain(img_bytes, page_number)
    except LLMFallbackError:
        return None, "None"

    engine = "Gemini" if _api_stats.get("last_engine_used") == "gemini" else "Ollama"
    if engine == "Ollama":
        model = _service_status.get("ollama_model", "unknown")
        engine = f"Ollama ({model})"
    return text, engine


def gemini_text_to_blocks(text: str, page_number: int, offset: int = 1) -> List[ContentBlock]:
    """Convert LLM output into ContentBlock objects."""
    if not text:
        return []

    blocks = _try_parse_gemini_json(text, offset)
    if blocks:
        return blocks

    out: List[ContentBlock] = []
    block_id = offset
    current_lines: List[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            if current_lines:
                bt = "\n".join(current_lines)
                ratio = bangla_char_ratio(bt)
                lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
                out.append(
                    ContentBlock(
                        block_id=block_id,
                        type="paragraph",
                        language=lang,
                        text=bt,
                        confidence=0.9,
                    )
                )
                block_id += 1
                current_lines = []
        else:
            current_lines.append(s)

    if current_lines:
        bt = "\n".join(current_lines)
        ratio = bangla_char_ratio(bt)
        lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
        out.append(
            ContentBlock(
                block_id=block_id,
                type="paragraph",
                language=lang,
                text=bt,
                confidence=0.9,
            )
        )

    return out


def _try_parse_gemini_json(text: str, offset: int) -> Optional[List[ContentBlock]]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines)

    try:
        data = json.loads(clean)
    except Exception:
        return None

    blocks_data = []
    if isinstance(data, dict):
        for key in ("content_blocks", "blocks", "content", "results"):
            if isinstance(data.get(key), list):
                blocks_data = data[key]
                break
    elif isinstance(data, list):
        blocks_data = data

    if not blocks_data:
        return None

    blocks: List[ContentBlock] = []
    for i, item in enumerate(blocks_data):
        if not isinstance(item, dict):
            continue
        text_val = (item.get("text") or "").strip()
        if not text_val:
            continue
        ratio = bangla_char_ratio(text_val)
        lang = item.get("language") or ("bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en"))
        blocks.append(
            ContentBlock(
                block_id=offset + i,
                type=item.get("type", "paragraph"),
                language=lang,
                text=text_val,
                confidence=float(item.get("confidence", 0.9)),
                is_handwritten=bool(item.get("is_handwritten", False)),
            )
        )

    return blocks or None
