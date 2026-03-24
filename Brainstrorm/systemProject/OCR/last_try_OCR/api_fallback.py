"""
API Fallback — Gemini + Local LLM (Ollama) for low-confidence pages.
Tries Gemini first, falls back to Ollama if Gemini fails or is unavailable.
Sends only individual page images, never entire PDFs.
Tracks API usage for cost control.
"""

import base64
import io
import logging
import time
import requests
from typing import List, Optional, Tuple

from . import config
from .models import ContentBlock, BBox

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# API USAGE TRACKING
# ══════════════════════════════════════════════════════════════════════
_api_stats = {
    "gemini_calls": 0,
    "gemini_tokens": 0,
    "gemini_errors": 0,
    "ollama_calls": 0,
    "ollama_errors": 0,
    "total_calls": 0,
    "total_tokens": 0,
    "errors": 0,
    "last_engine_used": None,  # 'gemini' | 'ollama' | None
}

_service_status = {
    "gemini_available": None,  # None = not checked, True/False = checked
    "gemini_error": None,
    "ollama_available": None,
    "ollama_model": None,
    "ollama_error": None,
}


def get_api_stats() -> dict:
    """Get API usage statistics."""
    return dict(_api_stats)


def get_service_status() -> dict:
    """Get service availability status."""
    return dict(_service_status)


def reset_api_stats():
    """Reset all API statistics."""
    for key in _api_stats:
        _api_stats[key] = 0


# ══════════════════════════════════════════════════════════════════════
# OLLAMA LOCAL LLM
# ══════════════════════════════════════════════════════════════════════


def _check_ollama_available() -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if Ollama is running and find an available vision model.
    Returns: (is_available, model_name, error_message)
    Note: Only vision-capable models can do OCR on images.
    """
    if not config.OLLAMA_ENABLED:
        return False, None, "Ollama disabled in config"

    # Vision model identifiers
    VISION_MODELS = [
        "llava",
        "bakllava",
        "moondream",
        "cogvlm",
        "minicpm",
        "qwen",
        "qwen2",
        "qwen2.5",
        "llama3.2-vision",
    ]

    try:
        # Check if Ollama is running
        resp = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, None, f"Ollama API returned {resp.status_code}"

        available_models = [m["name"] for m in resp.json().get("models", [])]
        if not available_models:
            return False, None, "No models installed in Ollama"

        # Find first available VISION model from priority list
        for model in config.OLLAMA_MODEL_PRIORITY:
            for avail in available_models:
                if model == avail or avail.startswith(model.split(":")[0]):
                    # Verify it's a vision model
                    model_base = avail.split(":")[0].lower()
                    if any(v in model_base for v in VISION_MODELS):
                        logger.info(f"Ollama vision model found: {avail}")
                        return True, avail, None

        # Check if ANY vision model is available
        for avail in available_models:
            model_base = avail.split(":")[0].lower()
            if any(v in model_base for v in VISION_MODELS):
                logger.info(f"Using available vision model: {avail}")
                return True, avail, None

        # No vision model found
        model_list = ", ".join(available_models[:3])
        return (
            False,
            None,
            f"No vision model found. Install with: ollama pull llava:7b (available: {model_list})",
        )

    except requests.exceptions.ConnectionError:
        return False, None, "Cannot connect to Ollama (run 'ollama serve')"
    except Exception as e:
        return False, None, str(e)


def _ocr_with_ollama(
    img_bytes: bytes,
    page_number: int,
    model: str,
) -> Optional[str]:
    """Send image to Ollama for OCR using a vision-capable model."""
    try:
        # Convert to base64
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Simple, fast prompt for local LLM
        prompt = "You are a document OCR expert. Extract ALL text from this image exactly as it appears.\nThis document contains Bangla (Bengali) and possibly English text.\n\nRules:\n1. Preserve every Bangla Unicode character exactly — matras, hasanta, conjuncts\n2. Preserve Bangla numerals (০১২৩৪৫৬৭৮৯) digit by digit — do NOT guess\n3. Keep original line breaks\n4. For tables, preserve rows with | separators\n5. Output ONLY the extracted text — no explanation, no markdown\n"

        # Check if it's a vision model
        is_vision = any(
            v in model.lower()
            for v in [
                "llava",
                "bakllava",
                "moondream",
                "cogvlm",
                "minicpm",
                "qwen",
                "llama3.2-vision",
            ]
        )

        if is_vision:
            # Vision model - can handle images directly
            payload = {
                "model": model,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2048,  # Reduced for speed
                    "num_ctx": 2048,  # Smaller context for speed
                },
            }
        else:
            # Text-only model cannot do OCR
            logger.warning(f"Model {model} is not vision-capable, skipping OCR")
            return None

        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=config.OLLAMA_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.error(f"Ollama returned {resp.status_code}: {resp.text[:200]}")
            _api_stats["ollama_errors"] += 1
            return None

        result = resp.json()
        text = result.get("response", "").strip()

        if text:
            _api_stats["ollama_calls"] += 1
            _api_stats["total_calls"] += 1
            logger.info(f"Ollama OCR page {page_number}: {len(text)} chars extracted")
            return text

        return None

    except requests.exceptions.Timeout:
        logger.error(f"Ollama timeout for page {page_number}")
        _api_stats["ollama_errors"] += 1
        return None
    except Exception as e:
        logger.error(f"Ollama OCR failed for page {page_number}: {e}")
        _api_stats["ollama_errors"] += 1
        return None


# ══════════════════════════════════════════════════════════════════════
# GEMINI OCR PROMPT
# ══════════════════════════════════════════════════════════════════════

_GEMINI_PROMPT = """Extract ALL text from this document image accurately.
You are an expert OCR engine specialized in extracting text from documents containing mixed Bangla (বাংলা) and English content, including handwritten text, printed text, tables, forms, boxes, columns, and images.

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

Now extract all text from the uploaded document and return ONLY the JSON.

CRITICAL RULES:
1. Bangla text: preserve EXACT characters including মাত্রা (matras), হসন্ত (hasanta), যুক্তবর্ণ (conjuncts)
2. Bengali numerals (০-৯): extract digit-by-digit, do NOT guess from context
   - ৩ vs ৫: ৩ has curved top, ৫ has FLAT top bar
   - ৮ vs ৪: ৮ has TWO loops, ৪ has ONE open curve
   - ৬ vs ৯: ৬ curves LEFT, ৯ curves RIGHT
3. Tables: preserve structure with rows and columns
4. Images/logos/seals: describe what you see
5. Handwritten text: mark as [HANDWRITTEN] if partially legible
6. Never skip any text, never hallucinate

Return the extracted text in reading order (top to bottom, left to right)."""


def _ocr_with_gemini(
    img_bytes: bytes,
    page_number: int,
) -> Optional[str]:
    """Send a single page image to Gemini for OCR."""
    if not config.GEMINI_API_KEY:
        _service_status["gemini_available"] = False
        _service_status["gemini_error"] = "GEMINI_API_KEY not set"
        return None

    try:
        from google import genai
        from PIL import Image

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = Image.open(io.BytesIO(img_bytes))

        # Resize if too large
        max_dim = config.MAX_IMAGE_DIMENSION
        if max(image.size) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.LANCZOS)

        for attempt in range(config.GEMINI_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[_GEMINI_PROMPT, image],
                )
                _api_stats["gemini_calls"] += 1
                _api_stats["total_calls"] += 1

                if hasattr(response, "usage_metadata"):
                    tokens = getattr(response.usage_metadata, "total_token_count", 0)
                    _api_stats["gemini_tokens"] += tokens
                    _api_stats["total_tokens"] += tokens

                text = response.text.strip() if response.text else ""
                if text:
                    _service_status["gemini_available"] = True
                    _service_status["gemini_error"] = None
                    logger.info(f"Gemini OCR page {page_number}: {len(text)} chars")
                    return text

            except Exception as e:
                err_str = str(e)
                logger.warning(
                    f"Gemini attempt {attempt + 1}/{config.GEMINI_MAX_RETRIES} failed: {err_str[:100]}"
                )

                # Check for quota/auth errors - don't retry these
                if any(
                    x in err_str.lower()
                    for x in ["quota", "api_key", "unauthorized", "forbidden"]
                ):
                    _service_status["gemini_available"] = False
                    _service_status["gemini_error"] = err_str[:100]
                    break

                if attempt < config.GEMINI_MAX_RETRIES - 1:
                    time.sleep(config.GEMINI_RETRY_DELAY * (attempt + 1))

        _api_stats["gemini_errors"] += 1
        _api_stats["errors"] += 1
        return None

    except ImportError:
        _service_status["gemini_available"] = False
        _service_status["gemini_error"] = "google-genai package not installed"
        logger.error("google-genai package not installed")
        return None
    except Exception as e:
        _api_stats["gemini_errors"] += 1
        _api_stats["errors"] += 1
        _service_status["gemini_error"] = str(e)[:100]
        logger.error(f"Gemini OCR failed for page {page_number}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════
# UNIFIED OCR INTERFACE
# ══════════════════════════════════════════════════════════════════════


def ocr_page_with_gemini(
    img_bytes: bytes,
    page_number: int,
) -> Optional[str]:
    """
    Primary OCR function — tries Gemini first, falls back to Ollama.
    This maintains backward compatibility with existing code.
    """
    result = None
    engine_used = None

    # Try Ollama first
    if config.OLLAMA_ENABLED:
        # Check Ollama availability
        if _service_status.get("ollama_available") is None:
            avail, model, err = _check_ollama_available()
            _service_status["ollama_available"] = avail
            _service_status["ollama_model"] = model
            _service_status["ollama_error"] = err
            config.set_status("ollama_available", avail)
            config.set_status("ollama_model", model)

        if _service_status.get("ollama_available") and _service_status.get(
            "ollama_model"
        ):
            result = _ocr_with_ollama(
                img_bytes, page_number, _service_status["ollama_model"]
            )
            if result:
                engine_used = f"Ollama ({_service_status['ollama_model']})"

    # Fallback to Gemini if Ollama failed
    if result is None and config.GEMINI_ENABLED and _service_status.get("gemini_available") is not False:
        result = _ocr_with_gemini(img_bytes, page_number)
        if result:
            engine_used = "Gemini"
            config.set_status("gemini_available", True)

    if result:
        logger.info(f"OCR page {page_number} completed with {engine_used}")
        # Track which engine actually produced the result
        if engine_used and engine_used.startswith("Ollama"):
            _api_stats["last_engine_used"] = "ollama"
        elif engine_used == "Gemini":
            _api_stats["last_engine_used"] = "gemini"
        else:
            _api_stats["last_engine_used"] = None
    else:
        logger.warning(
            f"All OCR engines (Gemini + Ollama) failed for page {page_number}"
        )
        _api_stats["last_engine_used"] = None
        _api_stats["errors"] += 1

    return result


def ocr_page_with_fallback(
    img_bytes: bytes,
    page_number: int,
) -> Tuple[Optional[str], str]:
    """
    OCR with explicit engine tracking.
    Chain: Local OCR (caller) → Gemini → Ollama (final fallback).
    Returns: (extracted_text, engine_name)
    """
    result = ocr_page_with_gemini(img_bytes, page_number)

    if result is None:
        return None, "None"

    last_engine = _api_stats.get("last_engine_used")
    if last_engine == "ollama":
        model = _service_status.get("ollama_model", "unknown")
        return result, f"Ollama ({model})"
    else:
        return result, "Gemini"


# ══════════════════════════════════════════════════════════════════════
# TEXT TO BLOCKS CONVERSION
# ══════════════════════════════════════════════════════════════════════


def gemini_text_to_blocks(
    text: str,
    page_number: int,
    offset: int = 1,
) -> List[ContentBlock]:
    """Convert LLM output into ContentBlock objects.
    Tries JSON parsing first, falls back to plain text splitting."""
    if not text:
        return []

    from .unicode_validator import bangla_char_ratio
    import json

    # Try to extract JSON from the response
    blocks = _try_parse_gemini_json(text, offset)
    if blocks:
        return blocks

    # Fallback: split by blank lines into text blocks
    blocks = []
    lines = text.split("\n")
    current_block_lines = []
    block_id = offset

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_block_lines:
                block_text = "\n".join(current_block_lines)
                bn_ratio = bangla_char_ratio(block_text)
                lang = "bn" if bn_ratio > 0.5 else ("mixed" if bn_ratio > 0.1 else "en")
                blocks.append(
                    ContentBlock(
                        block_id=block_id,
                        type="paragraph",
                        language=lang,
                        text=block_text,
                        confidence=0.90,
                    )
                )
                block_id += 1
                current_block_lines = []
        else:
            current_block_lines.append(stripped)

    if current_block_lines:
        block_text = "\n".join(current_block_lines)
        bn_ratio = bangla_char_ratio(block_text)
        lang = "bn" if bn_ratio > 0.5 else ("mixed" if bn_ratio > 0.1 else "en")
        blocks.append(
            ContentBlock(
                block_id=block_id,
                type="paragraph",
                language=lang,
                text=block_text,
                confidence=0.90,
            )
        )

    return blocks


def _try_parse_gemini_json(text: str, offset: int) -> Optional[List[ContentBlock]]:
    """Try to parse response as JSON with content blocks."""
    import json
    from .unicode_validator import bangla_char_ratio

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
    except (json.JSONDecodeError, ValueError):
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = clean.find(start_char)
            end_idx = clean.rfind(end_char)
            if start_idx != -1 and end_idx > start_idx:
                try:
                    data = json.loads(clean[start_idx : end_idx + 1])
                    break
                except (json.JSONDecodeError, ValueError):
                    continue
        else:
            return None

    blocks_data = []
    if isinstance(data, dict):
        for key in ("content_blocks", "blocks", "content", "pages", "results"):
            if key in data and isinstance(data[key], list):
                blocks_data = data[key]
                break
        if not blocks_data and "pages" in data and isinstance(data["pages"], list):
            for page in data["pages"]:
                if isinstance(page, dict):
                    for key in ("content_blocks", "blocks", "content"):
                        if key in page and isinstance(page[key], list):
                            blocks_data.extend(page[key])
                            break
    elif isinstance(data, list):
        blocks_data = data

    if not blocks_data:
        return None

    blocks = []
    for i, item in enumerate(blocks_data):
        if not isinstance(item, dict):
            continue
        text_val = item.get("text", "") or ""
        if not text_val.strip():
            continue
        block_type = item.get("type", "paragraph") or "paragraph"
        bn_ratio = bangla_char_ratio(text_val)
        lang = item.get("language") or (
            "bn" if bn_ratio > 0.5 else ("mixed" if bn_ratio > 0.1 else "en")
        )
        conf = float(item.get("confidence", 0.90))
        is_hw = bool(item.get("is_handwritten", False))

        blocks.append(
            ContentBlock(
                block_id=offset + i,
                type=block_type,
                language=lang,
                text=text_val,
                confidence=conf,
                is_handwritten=is_hw,
            )
        )

    return blocks if blocks else None
