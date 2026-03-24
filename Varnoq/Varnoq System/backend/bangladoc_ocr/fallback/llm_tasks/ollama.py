"""Ollama service checks and OCR calls."""

import base64
import io
import logging
import time
from typing import Optional, Tuple

import requests

from bangladoc_ocr import config

from .state import (
    get_service_status,
    increment_stat,
    set_service_status,
)

logger = logging.getLogger(__name__)


def check_ollama_available() -> Tuple[bool, Optional[str], Optional[str]]:
    if not config.OLLAMA_ENABLED:
        return False, None, "Ollama disabled"

    vision_keys = ("llava", "bakllava", "moondream", "minicpm", "qwen", "llama3.2-vision")

    try:
        response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            return False, None, f"Ollama API status {response.status_code}"

        available = [m["name"] for m in response.json().get("models", [])]
        if not available:
            return False, None, "No models installed"

        for expected in config.OLLAMA_MODEL_PRIORITY:
            for model_name in available:
                if expected == model_name or model_name.startswith(expected.split(":")[0]):
                    if any(k in model_name.lower() for k in vision_keys):
                        return True, model_name, None

        for model_name in available:
            if any(k in model_name.lower() for k in vision_keys):
                return True, model_name, None

        return False, None, "No vision model found"
    except requests.exceptions.ConnectionError:
        return False, None, "Cannot connect to Ollama"
    except Exception as exc:
        return False, None, str(exc)


def ensure_ollama_status(force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    now = time.time()
    last_checked = float(get_service_status("ollama_last_checked") or 0.0)
    cached = get_service_status("ollama_available")
    stale_unavailable = cached is False and (now - last_checked) >= config.OLLAMA_STATUS_RECHECK_SECONDS

    if force or cached is None or stale_unavailable:
        avail, model, err = check_ollama_available()
        set_service_status("ollama_available", avail)
        set_service_status("ollama_model", model)
        set_service_status("ollama_error", err)
        set_service_status("ollama_last_checked", now)
        config.set_status("ollama_available", avail)
        config.set_status("ollama_model", model)

    return (
        bool(get_service_status("ollama_available")),
        get_service_status("ollama_model"),
        get_service_status("ollama_error"),
    )


def call_ollama(
    model: str,
    image_b64: str,
    *,
    prompt: str,
    num_predict: int,
    num_ctx: int,
    timeout_s: int,
) -> Optional[str]:
    is_qwen = "qwen" in model.lower()
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
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
            "stream": False,
            "options": options,
        }
        endpoint = f"{config.OLLAMA_BASE_URL}/api/chat"
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": options,
        }
        endpoint = f"{config.OLLAMA_BASE_URL}/api/generate"

    response = requests.post(endpoint, json=payload, timeout=timeout_s)
    if response.status_code != 200:
        err_preview = (response.text or "").strip().replace("\n", " ")[:180]
        set_service_status("ollama_error", f"HTTP {response.status_code}: {err_preview}")
        return None

    data = response.json()
    if is_qwen:
        text = (data.get("message", {}).get("content") or "").strip()
    else:
        text = (data.get("response") or "").strip()
    if text:
        set_service_status("ollama_error", None)
    else:
        set_service_status("ollama_error", "Empty response from Ollama")
    return text or None


def ocr_with_ollama(img_bytes: bytes, page_number: int, model: str, prompt: str) -> Optional[str]:
    try:
        from PIL import Image as PILImage

        image = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
        long_edge = max(image.width, image.height)

        if long_edge > config.OLLAMA_MAX_IMAGE_EDGE:
            image.thumbnail((config.OLLAMA_MAX_IMAGE_EDGE, config.OLLAMA_MAX_IMAGE_EDGE), PILImage.LANCZOS)
        elif long_edge < config.OLLAMA_MIN_IMAGE_EDGE:
            scale = config.OLLAMA_MIN_IMAGE_EDGE / max(long_edge, 1)
            image = image.resize((int(image.width * scale), int(image.height * scale)), PILImage.LANCZOS)

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        text = call_ollama(
            model,
            b64,
            prompt=prompt,
            num_predict=1200,
            num_ctx=3072,
            timeout_s=config.OLLAMA_TIMEOUT,
        )

        if text and len(text) >= 20:
            increment_stat("ollama_calls")
            increment_stat("total_calls")
            logger.info("Ollama page %s: %d chars", page_number, len(text))
            return text

        increment_stat("ollama_errors")
        if not get_service_status("ollama_error"):
            set_service_status("ollama_error", "No usable OCR text returned")
        return None
    except Exception as exc:
        logger.warning("Ollama OCR failed on page %s: %s", page_number, exc)
        increment_stat("ollama_errors")
        set_service_status("ollama_error", str(exc))
        return None
