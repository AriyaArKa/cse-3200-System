"""LLM fallback chain: Ollama (local) first, then Gemini (cloud, optional)."""

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

# ── Prompt loading ─────────────────────────────────────────────────────────

def _load_prompt(path: Path, fallback: str, name: str) -> str:
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            logger.info("Loaded %s prompt (%d chars)", name, len(text))
            return text
        logger.warning("%s prompt file is empty: %s", name, path)
    else:
        logger.warning("%s prompt not found at %s — using fallback", name, path)
    return fallback

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "prompts" / "ocr_prompt.txt"
)
_OLLAMA_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "prompts" / "ollama_prompt.txt"
)
_OCR_PROMPT    = _load_prompt(_PROMPT_PATH, "Extract all text from this document image.", "Gemini OCR")
_OLLAMA_PROMPT = _load_prompt(_OLLAMA_PROMPT_PATH, _OCR_PROMPT, "Ollama OCR")

# ── Stats / Status ─────────────────────────────────────────────────────────

_api_stats = {
    "gemini_calls": 0, "gemini_tokens": 0, "gemini_errors": 0,
    "ollama_calls": 0, "ollama_errors": 0,
    "total_calls": 0, "total_tokens": 0, "errors": 0,
    "last_engine_used": None,
}

_service_status = {
    "gemini_available": None, "gemini_error": None,
    "ollama_available": None, "ollama_model": None, "ollama_error": None,
    "ollama_last_checked": 0.0,
}


def get_api_stats() -> dict:
    return dict(_api_stats)


def get_service_status() -> dict:
    return dict(_service_status)


def reset_api_stats() -> None:
    for key in _api_stats:
        _api_stats[key] = 0


# ── Ollama ─────────────────────────────────────────────────────────────────

def _check_ollama_available() -> Tuple[bool, Optional[str], Optional[str]]:
    if not config.OLLAMA_ENABLED:
        return False, None, "Ollama disabled in config"

    vision_keys = ("llava", "bakllava", "moondream", "minicpm", "qwen", "llama3.2-vision")

    try:
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, None, f"Ollama API returned {resp.status_code}"

        available = [m["name"] for m in resp.json().get("models", [])]
        if not available:
            return False, None, "No models installed in Ollama"

        for model in config.OLLAMA_MODEL_PRIORITY:
            for avail in available:
                if model == avail or avail.startswith(model.split(":")[0]):
                    if any(k in avail.split(":")[0].lower() for k in vision_keys):
                        return True, avail, None

        for avail in available:
            if any(k in avail.split(":")[0].lower() for k in vision_keys):
                return True, avail, None

        return False, None, "No vision model found. Run: ollama pull qwen2.5vl:7b"
    except requests.exceptions.ConnectionError:
        return False, None, "Cannot connect to Ollama (run: ollama serve)"
    except Exception as exc:
        return False, None, str(exc)


def ensure_ollama_status(force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """Refresh cached Ollama status when unknown or stale-unavailable."""
    now = time.time()
    last_checked = float(_service_status.get("ollama_last_checked") or 0.0)
    cached_available = _service_status.get("ollama_available")
    should_refresh = (
        force
        or cached_available is None
        or (
            cached_available is False
            and (now - last_checked) >= config.OLLAMA_STATUS_RECHECK_SECONDS
        )
    )

    if should_refresh:
        avail, model, err = _check_ollama_available()
        _service_status["ollama_available"] = avail
        _service_status["ollama_model"] = model
        _service_status["ollama_error"] = err
        _service_status["ollama_last_checked"] = now
        config.set_status("ollama_available", avail)
        config.set_status("ollama_model", model)

    return (
        bool(_service_status.get("ollama_available")),
        _service_status.get("ollama_model"),
        _service_status.get("ollama_error"),
    )


def _ocr_with_ollama(img_bytes: bytes, page_number: int, model: str) -> Optional[str]:
    try:
        from PIL import Image as PILImage

        base_img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
        img_pixels = base_img.width * base_img.height
        is_qwen = "qwen" in model.lower()
        min_chars = 50 if img_pixels > 600_000 else 20

        def _call_ollama(
            pil_img: "PILImage.Image",
            *,
            num_predict: int,
            num_ctx: int,
            timeout_s: int,
            prompt: str,
        ) -> Optional[str]:
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            options = {
                "num_predict": num_predict,
                "num_ctx": num_ctx,
                "temperature": 0.0,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            }

            if is_qwen:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
                    "stream": False,
                    "options": options,
                }
                endpoint = f"{config.OLLAMA_BASE_URL}/api/chat"
            else:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "options": options,
                }
                endpoint = f"{config.OLLAMA_BASE_URL}/api/generate"

            resp = requests.post(endpoint, json=payload, timeout=timeout_s)
            if resp.status_code != 200:
                return None

            result = resp.json()
            text = (
                (result.get("message", {}).get("content") or "").strip()
                if is_qwen
                else (result.get("response") or "").strip()
            )
            return text or None

        # qwen2.5vl on CPU can fail with large contexts/images. Use progressive
        # profiles from stability-first to quality and stop on first valid success.
        profiles = [
            (config.OLLAMA_MAX_IMAGE_EDGE, 1200, 3072, min(config.OLLAMA_TIMEOUT, 80)),
            (1024, 900, 2048, min(config.OLLAMA_TIMEOUT, 75)),
            (config.OLLAMA_MIN_IMAGE_EDGE, 700, 1536, min(config.OLLAMA_TIMEOUT, 75)),
            (1536, 1500, 4096, min(config.OLLAMA_TIMEOUT, 110)),
        ]

        for long_edge, num_predict, num_ctx, timeout_s in profiles:
            pil_img = base_img.copy()
            current_long = max(pil_img.width, pil_img.height)
            if current_long > long_edge:
                pil_img.thumbnail((long_edge, long_edge), PILImage.LANCZOS)
            elif current_long < config.OLLAMA_MIN_IMAGE_EDGE:
                scale = config.OLLAMA_MIN_IMAGE_EDGE / max(current_long, 1)
                pil_img = pil_img.resize(
                    (int(pil_img.width * scale), int(pil_img.height * scale)),
                    PILImage.LANCZOS,
                )

            try:
                text = _call_ollama(
                    pil_img,
                    num_predict=num_predict,
                    num_ctx=num_ctx,
                    timeout_s=timeout_s,
                    prompt=_OLLAMA_PROMPT,
                )
            except requests.exceptions.Timeout:
                logger.warning(
                    "Ollama timeout page %s (edge=%s, ctx=%s)",
                    page_number,
                    long_edge,
                    num_ctx,
                )
                continue
            except Exception as exc:
                logger.warning(
                    "Ollama request failed page %s (edge=%s): %s",
                    page_number,
                    long_edge,
                    exc,
                )
                continue

            if text and len(text) >= min_chars:
                _api_stats["ollama_calls"] += 1
                _api_stats["total_calls"] += 1
                logger.info(
                    "Ollama page %s: %d chars (edge=%s, ctx=%s)",
                    page_number,
                    len(text),
                    long_edge,
                    num_ctx,
                )
                return text

            if text:
                logger.warning(
                    "Ollama short output page %s: %d chars (edge=%s)",
                    page_number,
                    len(text),
                    long_edge,
                )

        # Rescue pass: OCR three overlapping vertical tiles when full-page calls
        # return only short outputs on dense Bangla pages.
        if img_pixels > 500_000:
            w, h = base_img.size
            stride = h // 3
            overlap = max(40, int(h * 0.08))
            tile_prompt = (
                "OCR this document region exactly. Output only visible text in reading order. "
                "No explanation, no markdown, no guesses."
            )
            parts: list[str] = []
            for idx in range(3):
                top = max(0, idx * stride - overlap)
                bottom = min(h, (idx + 1) * stride + overlap)
                tile = base_img.crop((0, top, w, bottom))
                long_edge = max(tile.size)
                if long_edge > 1200:
                    tile.thumbnail((1200, 1200), PILImage.LANCZOS)
                try:
                    text = _call_ollama(
                        tile,
                        num_predict=800,
                        num_ctx=2048,
                        timeout_s=min(config.OLLAMA_TIMEOUT, 60),
                        prompt=tile_prompt,
                    )
                except Exception as exc:
                    logger.warning("Ollama tile %s failed page %s: %s", idx + 1, page_number, exc)
                    continue

                if text and len(text) >= 25:
                    parts.append(text)

            if parts:
                merged_lines: list[str] = []
                seen: set[str] = set()
                for part in parts:
                    for raw in part.splitlines():
                        line = raw.strip()
                        if not line:
                            continue
                        key = line.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        merged_lines.append(line)

                merged_text = "\n".join(merged_lines).strip()
                if len(merged_text) >= min_chars * 2:
                    _api_stats["ollama_calls"] += 1
                    _api_stats["total_calls"] += 1
                    logger.info(
                        "Ollama page %s rescued via tiled OCR: %d chars",
                        page_number,
                        len(merged_text),
                    )
                    return merged_text

        _api_stats["ollama_errors"] += 1
        return None

    except Exception as exc:
        logger.warning("Ollama OCR failed (page %s): %s", page_number, exc)
        _api_stats["ollama_errors"] += 1
        return None


def refine_ollama_ocr_text(text: str, model: str) -> str:
    """Run a lightweight text-only cleanup pass on Ollama OCR output."""
    src = (text or "").strip()
    if not src or len(src) < 120 or bangla_char_ratio(src) < 0.2:
        return src

    instruction = (
        "Fix only obvious OCR mistakes in this Bangla text. "
        "Preserve all numbers, dates, emails, URLs, and English words exactly as-is. "
        "Do not add new facts. Return corrected plain text only."
    )

    try:
        is_qwen = "qwen" in model.lower()
        options = {
            "num_predict": 1100,
            "num_ctx": 3072,
            "temperature": 0.0,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        }

        if is_qwen:
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": f"{instruction}\n\n--- OCR TEXT START ---\n{src}\n--- OCR TEXT END ---",
                }],
                "stream": False,
                "options": options,
            }
            endpoint = f"{config.OLLAMA_BASE_URL}/api/chat"
        else:
            payload = {
                "model": model,
                "prompt": f"{instruction}\n\n--- OCR TEXT START ---\n{src}\n--- OCR TEXT END ---",
                "stream": False,
                "options": options,
            }
            endpoint = f"{config.OLLAMA_BASE_URL}/api/generate"

        resp = requests.post(endpoint, json=payload, timeout=min(config.OLLAMA_TIMEOUT, 45))
        if resp.status_code != 200:
            return src

        data = resp.json()
        refined = (
            (data.get("message", {}).get("content") or "").strip()
            if is_qwen
            else (data.get("response") or "").strip()
        )

        if not refined:
            return src

        if len(refined) < int(len(src) * 0.6) or len(refined) > int(len(src) * 1.7):
            return src

        return refined
    except Exception:
        return src


# ── Gemini ─────────────────────────────────────────────────────────────────

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
                    logger.info("Gemini page %s: %d chars", page_number, len(text))
                    return text
            except Exception as exc:
                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    time.sleep(config.GEMINI_RETRY_DELAY)
                else:
                    logger.warning("Gemini OCR failed: %s", exc)

        _api_stats["gemini_errors"] += 1
        return None
    except Exception as exc:
        logger.warning("Gemini unavailable: %s", exc)
        _api_stats["gemini_errors"] += 1
        return None


# ── Unified chain ──────────────────────────────────────────────────────────

def ocr_with_llm_chain(img_bytes: bytes, page_number: int) -> str:
    """Try Ollama first (local, no rate limit), then Gemini if enabled."""
    avail, model, _ = ensure_ollama_status(force=False)

    if avail and model:
        text = _ocr_with_ollama(img_bytes, page_number, model)
        if text:
            _api_stats["last_engine_used"] = "ollama"
            return text

    if config.GEMINI_ENABLED and config.GEMINI_API_KEY:
        text = _ocr_with_gemini(img_bytes, page_number)
        if text:
            _api_stats["last_engine_used"] = "gemini"
            return text

    _api_stats["errors"] += 1
    _api_stats["last_engine_used"] = None
    raise LLMFallbackError(f"All LLM engines failed on page {page_number}")


def ocr_page_with_fallback(img_bytes: bytes, page_number: int) -> Tuple[Optional[str], str]:
    """Compatibility wrapper returning (text, engine_name)."""
    try:
        text = ocr_with_llm_chain(img_bytes, page_number)
    except LLMFallbackError:
        return None, "None"

    last = _api_stats.get("last_engine_used")
    if last == "ollama":
        model = _service_status.get("ollama_model", "unknown")
        return text, f"Ollama ({model})"
    return text, "Gemini"


# ── Text → blocks ──────────────────────────────────────────────────────────

def gemini_text_to_blocks(text: str, page_number: int, offset: int = 1) -> List[ContentBlock]:
    if not text:
        return []

    blocks = _try_parse_json(text, offset)
    if blocks:
        return blocks

    out: List[ContentBlock] = []
    block_id = offset
    current: List[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            if current:
                bt = "\n".join(current)
                ratio = bangla_char_ratio(bt)
                lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
                out.append(ContentBlock(block_id=block_id, type="paragraph",
                                        language=lang, text=bt, confidence=0.9))
                block_id += 1
                current = []
        else:
            current.append(s)

    if current:
        bt = "\n".join(current)
        ratio = bangla_char_ratio(bt)
        lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
        out.append(ContentBlock(block_id=block_id, type="paragraph",
                                language=lang, text=bt, confidence=0.9))
    return out


def _try_parse_json(text: str, offset: int) -> Optional[List[ContentBlock]]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(
            lines[1:] if lines[0].startswith("```") else lines
        ).rstrip("`").strip()

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

    blocks = []
    for i, item in enumerate(blocks_data):
        if not isinstance(item, dict):
            continue
        tv = (item.get("text") or "").strip()
        if not tv:
            continue
        ratio = bangla_char_ratio(tv)
        lang = item.get("language") or (
            "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
        )
        blocks.append(ContentBlock(
            block_id=offset + i,
            type=item.get("type", "paragraph"),
            language=lang,
            text=tv,
            confidence=float(item.get("confidence", 0.9)),
            is_handwritten=bool(item.get("is_handwritten", False)),
        ))
    return blocks or None


# ── Startup check ──────────────────────────────────────────────────────────

def _warn_if_ollama_unavailable() -> None:
    avail, model, err = ensure_ollama_status(force=True)
    if avail:
        logger.info("✓ Ollama ready: %s", model)
    else:
        logger.warning(
            "⚠  Ollama not available: %s\n"
            "   Bangla pages will use EasyOCR only (lower accuracy).\n"
            "   Fix: ollama pull qwen2.5vl:7b && ollama serve",
            err,
        )

try:
    _warn_if_ollama_unavailable()
except Exception:
    pass