"""Image description module: Ollama first, Gemini fallback."""

import base64
import io
import logging

import httpx
from PIL import Image

from bangladoc_ocr import config

logger = logging.getLogger(__name__)


def classify_heuristic(width: int, height: int) -> str:
    if width == 0 or height == 0:
        return "unknown"
    ratio = width / height
    if 0.85 < ratio < 1.15 and max(width, height) < 250:
        return "seal"
    if width < 200 and height < 80:
        return "signature"
    if ratio > 2.5:
        return "table_or_chart"
    return "photo"


async def describe(img_bytes: bytes, img_type: str = "unknown") -> str:
    del img_type
    text = await _ollama(img_bytes)
    if text:
        return text
    return await _gemini(img_bytes)


async def _ollama(img_bytes: bytes) -> str:
    if not config.OLLAMA_ENABLED:
        return ""

    try:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.OLLAMA_IMAGE_MODEL,
                    "prompt": (
                        "Describe this image in 1-2 sentences. "
                        "For seals: include emblem and visible text. "
                        "For signatures: state handwritten signature. "
                        "For charts: summarize data type. "
                        "Keep under 50 words."
                    ),
                    "images": [b64],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 80},
                },
            )

        if response.status_code == 200:
            return (response.json().get("response") or "").strip()[:300]
    except Exception as exc:
        logger.debug("Ollama image description failed: %s", exc)

    return ""


async def _gemini(img_bytes: bytes) -> str:
    if not config.GEMINI_ENABLED or not config.GEMINI_API_KEY:
        return ""

    try:
        from google import genai

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        if max(image.size) > 1024:
            image.thumbnail((1024, 1024), Image.LANCZOS)

        result = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                "Describe this image briefly. If there is text, extract it. Keep under 80 words.",
                image,
            ],
        )
        return (result.text or "").strip()[:300]
    except Exception as exc:
        logger.debug("Gemini image description failed: %s", exc)

    return ""
