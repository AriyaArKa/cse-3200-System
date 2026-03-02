"""
Google Gemini Vision API integration for OCR + structured extraction.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import google.generativeai as genai  # type: ignore
from PIL import Image  # type: ignore

from app.utils import GEMINI_API_KEY, MAX_RETRIES, logger

# ────────────────────────── Gemini configuration ──────────────────────────

genai.configure(api_key=GEMINI_API_KEY)

_MODEL_NAME = "gemini-2.0-flash"
_GENERATION_CONFIG = genai.GenerationConfig(
    temperature=0.1,
    top_p=0.95,
    max_output_tokens=8192,
)

_model = genai.GenerativeModel(
    model_name=_MODEL_NAME,
    generation_config=_GENERATION_CONFIG,
)

# ──────────────────────── Prompt engineering ──────────────────────────────

SYSTEM_PROMPT = """You are a world-class OCR and document analysis engine.
You MUST respond with ONLY valid JSON — no markdown, no code fences, no explanation, no extra text.

Analyse the provided document image and return a JSON object with EXACTLY this structure:

{
  "page_number": <integer>,
  "raw_text": "<all visible text on the page, preserving order>",
  "tables": [
    {
      "headers": ["<col1>", "<col2>", ...],
      "rows": [["<val1>", "<val2>", ...], ...]
    }
  ],
  "key_value_pairs": {
    "<key>": "<value>",
    ...
  },
  "line_items": [
    {
      "description": "<string>",
      "quantity": "<string>",
      "unit_price": "<string>",
      "total": "<string>"
    }
  ],
  "confidence_score": <float between 0 and 1>,
  "detected_document_type": "<invoice | government_notice | table | form | receipt | letter | report | unknown>"
}

RULES:
- Always include ALL fields even if empty (use empty list [] or empty dict {}).
- Tables: extract every table you see. If none, return empty list.
- Key-value pairs: extract labelled fields (e.g., Invoice #, Date, Total).
- Line items: extract itemised rows from invoices/receipts. If none, return empty list.
- confidence_score: your self-assessed confidence in extraction accuracy (0.0–1.0).
- detected_document_type: classify the document.
- Do NOT wrap the JSON in code fences or markdown.
- Output ONLY the JSON object, nothing else."""

CORRECTION_PROMPT = """Your previous response was not valid JSON.
Return ONLY a corrected valid JSON object following the exact schema requested.
Do NOT include any explanation or markdown. Output raw JSON only."""


# ──────────────────────────── JSON extraction ─────────────────────────────


def _extract_json(text: str) -> dict[str, Any]:
    """
    Try to pull a JSON object out of the model's response text.
    Handles cases where the model wraps the JSON in code fences.
    """
    # Strip markdown code fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    return json.loads(text)


# ─────────────────── Single-page OCR with retry logic ────────────────────


async def ocr_page(image_path: Path, page_number: int) -> dict[str, Any]:
    """
    Send one page image to Gemini Vision and return structured JSON.

    Retries up to MAX_RETRIES times if the response is not valid JSON.
    """
    img = Image.open(image_path)

    prompt = f"{SYSTEM_PROMPT}\n\nThis is page {page_number}."

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Gemini request for page %d (attempt %d/%d)",
                page_number,
                attempt,
                MAX_RETRIES,
            )

            # genai SDK is synchronous – run in thread to keep async
            response = await asyncio.to_thread(_model.generate_content, [prompt, img])

            if not response.text:
                raise ValueError("Gemini returned empty response.")

            result = _extract_json(response.text)
            result["page_number"] = page_number  # enforce correct page number
            logger.info("Page %d OCR succeeded (attempt %d).", page_number, attempt)
            return result

        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning(
                "Page %d: invalid JSON on attempt %d – retrying with correction prompt.",
                page_number,
                attempt,
            )
            # On retry, send a correction prompt
            prompt = (
                f"{CORRECTION_PROMPT}\n\n"
                f"Previously you returned:\n{response.text}\n\n"
                f"Fix it and return ONLY valid JSON for page {page_number}."
            )

        except Exception as exc:
            last_error = exc
            logger.error(
                "Page %d: Gemini error on attempt %d: %s",
                page_number,
                attempt,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)  # exponential back-off

    # All retries exhausted — return a minimal fallback
    logger.error(
        "Page %d: all %d attempts failed. Returning fallback.", page_number, MAX_RETRIES
    )
    return {
        "page_number": page_number,
        "raw_text": "",
        "tables": [],
        "key_value_pairs": {},
        "line_items": [],
        "confidence_score": 0.0,
        "detected_document_type": "unknown",
        "_error": str(last_error),
    }


# ───────────────────── Multi-page parallel OCR ───────────────────────────


async def ocr_all_pages(
    image_paths: list[Path],
) -> list[dict[str, Any]]:
    """
    Run OCR on all pages concurrently (bounded to avoid rate limits).

    Returns a list of per-page result dicts ordered by page number.
    """
    semaphore = asyncio.Semaphore(5)  # max 5 concurrent Gemini requests

    async def _sem_ocr(path: Path, pg: int) -> dict[str, Any]:
        async with semaphore:
            return await ocr_page(path, pg)

    tasks = [_sem_ocr(path, idx) for idx, path in enumerate(image_paths, start=1)]

    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda r: r.get("page_number", 0))
