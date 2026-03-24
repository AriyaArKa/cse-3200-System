"""
OCR Engines Module for PerfectOCR.
Provides both Gemini and GPT-4o vision-based OCR.
Each engine sends a page image with the master prompt and returns structured JSON.
"""

import json
import re
import time
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from . import config

logger = logging.getLogger(__name__)

# ── MASTER PROMPT ───────────────────────────────────────
MASTER_PROMPT = """You are an expert OCR engine specialized in extracting text from documents containing mixed Bangla (বাংলা) and English content, including handwritten text, printed text, tables, forms, boxes, columns, and images.

## YOUR TASK
Extract ALL text from the provided document page image with 100% accuracy and return it as structured JSON.

## EXTRACTION RULES

### Text Accuracy
- Extract Bangla text EXACTLY as written — every mattra (মাত্রা), hasanta (্), nukta, and conjunct must be preserved perfectly
- Do NOT transliterate, translate, or normalize any text
- Preserve all English text exactly including casing, punctuation, and numbers
- Never skip or hallucinate any text

### CRITICAL: Bengali Numeral Accuracy (HIGHEST PRIORITY)
Bengali digits (০-৯) are THE #1 SOURCE OF OCR ERRORS. You MUST extract them with EXTREME care:

**Visual Characteristics:**
- ০ (0): Looks like an oval/circle at the top of the line
- ১ (1): Single vertical or slightly curved line
- ২ (2): Has ONE curved belly
- ৩ (3): Has TWO curved bellies, looks like "3" rotated
- ৪ (4): Single OPEN curve like a "C" or backwards "৩"
- ৫ (5): Has a FLAT HORIZONTAL TOP stroke, then curves down
- ৬ (6): Curves LEFT at the bottom
- ৭ (7): Looks similar to "7" but with top hook
- ৮ (8): Two loops/circles stacked, like "8"
- ৯ (9): Curves RIGHT at the bottom

**MOST COMMONLY CONFUSED PAIRS:**
- ৩ (3) vs ৫ (5): ৩ = curved top, ৫ = FLAT top bar
- ৮ (8) vs ৪ (4): ৮ = TWO loops, ৪ = ONE open curve
- ৬ (6) vs ৯ (9): ৬ = curves LEFT, ৯ = curves RIGHT
- ২ (2) vs ৩ (3): ২ = ONE belly, ৩ = TWO bellies

**EXTRACTION PROTOCOL:**
1. Look at EACH digit individually — do not guess from context
2. For dates like ২৮/০৯/২০২৩, verify: day (১-৩১), month (০১-১২), year
3. If you extract ১৩ as a month or ৩২ as a day, you made a mistake — recheck
4. For serial numbers, compare each digit to the visual guide above
5. When in doubt between ৩ and ৫, look for the flat top bar (৫) vs curved top (৩)
6. NEVER auto-correct digits based on context — extract what you SEE, digit by digit

### Handwritten Text Extraction
- Handwritten text requires EXTRA attention — zoom in mentally on each character
- For handwritten SIGNATURES: describe what the signature looks like rather than guessing letters
  Example: instead of "Aduayan", write "[Signature of the official]" or the actual name if clearly readable
- For handwritten dates: cross-reference with printed dates nearby for verification
- For handwritten annotations/notes: extract character by character carefully
- Set is_handwritten: true for ALL handwritten blocks
- If handwritten text is partially legible, extract what you CAN read and mark the rest as [ILLEGIBLE]
- For handwritten Bangla, contextual word-level correction is allowed (e.g., if "বিশ্ববিদ্যাল" is written, complete it as "বিশ্ববিদ্যালয়")

### Layout Detection
Identify and preserve the document structure:
- Tables: Detect rows, columns, merged cells, headers
- Forms: Detect labels, input fields, checkboxes, filled values
- Columns: Detect multi-column newspaper or document layout
- Boxes/Sections: Detect bordered sections, callout boxes
- Paragraphs: Preserve paragraph breaks
- Lists: Detect ordered/unordered lists
- Headers/Footers: Separate from body content
- Page numbers, stamps, watermarks: Capture separately

### Image/Logo/Seal Description
- If you see an image, logo, seal, emblem, photograph, or any visual element:
  - Set type to "image"
  - In "text", provide a DETAILED description of what the image shows
  - Example: "University emblem/logo of Khulna University of Engineering & Technology (KUET) showing the official seal with Bengali text"
  - Example: "Photograph of a person in formal attire"
  - Example: "Official government seal with national emblem"  
  - NEVER just write "[IMAGE]" — always describe what you see

### Reading Order
Always follow natural reading order: top-to-bottom, left-to-right for English, right-to-left awareness for mixed scripts if needed.

## OUTPUT FORMAT

Return ONLY valid JSON. No explanation, no markdown, no code fences. Start directly with {

{
  "page_number": 1,
  "content_blocks": [
    {
      "block_id": 1,
      "type": "header|paragraph|table|form|list|box|footer|divider|image|signature",
      "position": "top|middle|bottom|left-column|right-column|full-width",
      "language": "bn|en|mixed",
      "confidence": "high|medium|low",
      "text": "extracted text here",
      "is_handwritten": false
    }
  ],
  "tables": [
    {
      "block_id": 2,
      "type": "table",
      "rows": 3,
      "columns": 4,
      "has_header_row": true,
      "data": [["H1","H2"],["C1","C2"]],
      "merged_cells": []
    }
  ],
  "forms": [
    {
      "block_id": 3,
      "fields": [
        {"label": "নাম", "value": "করিম", "is_filled": true}
      ]
    }
  ],
  "full_text_reading_order": "all text in order with \\n for line breaks",
  "extraction_notes": ["any warnings or low-confidence areas"]
}

## SPECIAL INSTRUCTIONS

1. If a cell or field is empty, return "" — never return null for text fields
2. If text is struck through, wrap it like: "~~strikethrough text~~"
3. If a region has an image/logo/seal, set type to "image" and DESCRIBE it in "text" (never just "[IMAGE]")
4. If you see a checkbox, represent it as "☑" for checked and "☐" for unchecked
5. If handwritten text is illegible, write "[ILLEGIBLE]" for that portion only
6. For handwritten signatures, use type "signature" and describe or transcribe accurately
7. Never skip any block — even decorative lines should be noted as "type": "divider"
8. For multi-column layouts, treat each column as a separate block with "position": "left-column" or "right-column"
9. If uncertain about any Bangla character, always prefer the contextually correct word
10. DOUBLE-CHECK all Bengali numerals (০-৯) — this is the #1 source of OCR errors
11. For dates: verify day (১-৩১), month (০১-১২), year format consistency
12. Preserve the exact format of numbers, dates, and reference numbers as they appear

Now extract all text from the uploaded document and return ONLY the JSON."""


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences and extract pure JSON."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_ocr_response(text: str, page_num: int) -> Dict[str, Any]:
    """Parse OCR response text into structured dict."""
    cleaned = _clean_json_response(text)
    try:
        result = json.loads(cleaned)
        # Ensure page_number is set
        if "page_number" not in result:
            result["page_number"] = page_num
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed for page {page_num}: {e}")
        # Return raw text as a single block
        return {
            "page_number": page_num,
            "content_blocks": [
                {
                    "block_id": 1,
                    "type": "paragraph",
                    "position": "full-width",
                    "language": "mixed",
                    "confidence": "low",
                    "text": cleaned,
                    "is_handwritten": False,
                }
            ],
            "tables": [],
            "forms": [],
            "full_text_reading_order": cleaned,
            "extraction_notes": [f"JSON parse failed: {str(e)}. Raw text preserved."],
        }


# ── GEMINI OCR ENGINE ───────────────────────────────────
class GeminiOCREngine:
    """OCR engine using Google Gemini vision model."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(api_key=config.GEMINI_API_KEY)
                logger.info("Gemini client initialized")
            except Exception as e:
                logger.error(f"Gemini client init failed: {e}")
                raise
        return self._client

    def extract_page(self, image_b64: str, page_num: int) -> Dict[str, Any]:
        """
        Extract text from a page image using Gemini.

        Args:
            image_b64: Base64-encoded PNG image
            page_num: Page number (1-indexed)

        Returns:
            Structured OCR result dict
        """
        import base64

        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[
                        MASTER_PROMPT,
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64,
                            }
                        },
                    ],
                )
                text = response.text.strip()
                result = _parse_ocr_response(text, page_num)
                logger.info(f"Gemini extracted page {page_num}")
                return result

            except Exception as e:
                wait_time = config.GEMINI_RETRY_DELAY * (2**attempt)
                logger.warning(
                    f"Gemini attempt {attempt + 1}/{config.GEMINI_MAX_RETRIES} "
                    f"failed for page {page_num}: {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        logger.error(f"Gemini OCR failed for page {page_num} after all retries")
        return {
            "page_number": page_num,
            "content_blocks": [],
            "tables": [],
            "forms": [],
            "full_text_reading_order": "",
            "extraction_notes": [
                f"Gemini OCR failed after {config.GEMINI_MAX_RETRIES} attempts"
            ],
        }


# ── GPT-4o OCR ENGINE ──────────────────────────────────
class GPT4oOCREngine:
    """OCR engine using OpenAI GPT-4o vision model."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI

                kwargs = {"api_key": config.OPENAI_API_KEY}
                if config.OPENAI_BASE_URL:
                    kwargs["base_url"] = config.OPENAI_BASE_URL
                self._client = OpenAI(**kwargs)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error(f"OpenAI client init failed: {e}")
                raise
        return self._client

    def extract_page(self, image_b64: str, page_num: int) -> Dict[str, Any]:
        """
        Extract text from a page image using GPT-4o.

        Args:
            image_b64: Base64-encoded PNG image
            page_num: Page number (1-indexed)

        Returns:
            Structured OCR result dict
        """
        for attempt in range(config.OPENAI_MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": MASTER_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_b64}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=config.OPENAI_MAX_TOKENS,
                )
                text = response.choices[0].message.content.strip()
                result = _parse_ocr_response(text, page_num)
                logger.info(f"GPT-4o extracted page {page_num}")
                return result

            except Exception as e:
                error_msg = str(e)
                # Detect specific error types for better logging
                if "rate_limit" in error_msg.lower() or "429" in error_msg:
                    logger.error(
                        f"GPT-4o RATE LIMIT hit on page {page_num}: {error_msg}"
                    )
                elif (
                    "auth" in error_msg.lower()
                    or "401" in error_msg
                    or "api_key" in error_msg.lower()
                ):
                    logger.error(f"GPT-4o AUTH ERROR on page {page_num}: {error_msg}")
                    # Don't retry auth errors
                    break
                elif (
                    "quota" in error_msg.lower()
                    or "billing" in error_msg.lower()
                    or "insufficient" in error_msg.lower()
                ):
                    logger.error(
                        f"GPT-4o QUOTA/BILLING ERROR on page {page_num}: {error_msg}"
                    )
                    break
                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    logger.warning(f"GPT-4o TIMEOUT on page {page_num}: {error_msg}")
                else:
                    logger.warning(f"GPT-4o ERROR on page {page_num}: {error_msg}")

                wait_time = config.OPENAI_RETRY_DELAY * (2**attempt)
                logger.warning(
                    f"GPT-4o attempt {attempt + 1}/{config.OPENAI_MAX_RETRIES} "
                    f"failed for page {page_num}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        logger.error(f"GPT-4o OCR failed for page {page_num} after all retries")
        return {
            "page_number": page_num,
            "content_blocks": [],
            "tables": [],
            "forms": [],
            "full_text_reading_order": "",
            "extraction_notes": [
                f"GPT-4o OCR failed after {config.OPENAI_MAX_RETRIES} attempts"
            ],
        }


# ── Usage Tracker ───────────────────────────────────────
class OCRUsageTracker:
    """Track API usage for both models."""

    def __init__(self):
        self.gemini_calls = 0
        self.gpt4o_calls = 0
        self.gemini_failures = 0
        self.gpt4o_failures = 0
        self.correction_calls = 0
        self.cache_hits = 0
        self.tesseract_only_pages = 0  # Pages processed by Tesseract without AI

    def record_gemini_call(self, success: bool = True):
        if success:
            self.gemini_calls += 1
        else:
            self.gemini_failures += 1

    def record_gpt4o_call(self, success: bool = True):
        if success:
            self.gpt4o_calls += 1
        else:
            self.gpt4o_failures += 1

    def record_correction_call(self):
        self.correction_calls += 1

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_tesseract_only(self):
        """Record that a page was successfully processed by Tesseract alone (no AI needed)."""
        self.tesseract_only_pages += 1

    @property
    def total_api_calls(self) -> int:
        return self.gemini_calls + self.gpt4o_calls + self.correction_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gemini_calls": self.gemini_calls,
            "gpt4o_calls": self.gpt4o_calls,
            "gemini_failures": self.gemini_failures,
            "gpt4o_failures": self.gpt4o_failures,
            "correction_calls": self.correction_calls,
            "cache_hits": self.cache_hits,
            "tesseract_only_pages": self.tesseract_only_pages,
            "total_api_calls": self.total_api_calls,
        }
