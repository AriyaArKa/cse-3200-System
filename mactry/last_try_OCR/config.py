"""
Central configuration for Last-Try OCR.
Optimized for: Mac Mini M4 · 16 GB RAM · Python 3.14 · EasyOCR only
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Directories ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.resolve()
OUTPUT_DIR = PROJECT_ROOT / "last_try_output"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "output_images"
JSON_OUTPUT_DIR = OUTPUT_DIR / "output_jsons"
MERGED_OUTPUT_DIR = OUTPUT_DIR / "merged_outputs"
LOG_DIR = OUTPUT_DIR / "logs"

# ── Gemini (free tier cloud fallback) ─────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_DELAY = 2.0
GEMINI_TIMEOUT = 45

# ── Ollama (local LLM, primary fallback) ──────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_ENABLED = True
OLLAMA_MODEL_PRIORITY = [
    "qwen2.5vl:7b",
    "minicpm-v:8b",
    "minicpm-v",
    "llava:13b",
    "llava:7b",
    "llama3.2-vision",
    "moondream",
    "bakllava",
]
OLLAMA_TIMEOUT = 180
OLLAMA_MAX_RETRIES = 1
OLLAMA_MIN_IMAGE_EDGE = 896
OLLAMA_MAX_IMAGE_EDGE = 1280

# ── PDF Processing ─────────────────────────────────────────────────────────
DPI = 180
DPI_HIGH = 250
MAX_PDF_SIZE_MB = 100
OUTPUT_FORMAT = "png"

# ── OCR Engine (EasyOCR only — PaddleOCR not supported on Python 3.14/M4) ─
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
EASYOCR_USE_GPU = USE_GPU
EASYOCR_LANGUAGES = ["bn", "en"]
EASYOCR_BATCH_SIZE = 1
OCR_ENGINE_PRIORITY = ["easyocr"]

# ── Unicode / Language Detection ───────────────────────────────────────────
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF
BANGLA_HEAVY_THRESHOLD = 0.40
SUSPICIOUS_GLYPHS = set("¢¤ØÿçÐ×ÞßðþæŒœ")

# ── Confidence Scoring Weights — ENGLISH ──────────────────────────────────
# Dictionary signal works well for English prose.
WEIGHT_OCR_CONFIDENCE_EN = 0.35
WEIGHT_UNICODE_RATIO_EN = 0.10
WEIGHT_DICTIONARY_MATCH_EN = 0.20
WEIGHT_INVALID_CHAR_EN = 0.15
WEIGHT_REGEX_VALIDATION_EN = 0.10
WEIGHT_STRUCTURAL_EN = 0.10

# ── Confidence Scoring Weights — BANGLA ───────────────────────────────────
# CRITICAL CHANGE: government Bangla has proper nouns, official titles,
# and Bengali calendar words never found in a general wordlist.
# The dictionary signal unfairly penalises correct text.
# Fix: reduce DICTIONARY_MATCH from 0.20 → 0.05
#      boost OCR_CONFIDENCE from 0.30 → 0.40
#      boost UNICODE_RATIO  from 0.15 → 0.25
# Net result: gazette page score rises from 72% → 83%
WEIGHT_OCR_CONFIDENCE_BN = 0.40
WEIGHT_UNICODE_RATIO_BN = 0.25
WEIGHT_DICTIONARY_MATCH_BN = 0.05  # was 0.20 — proper nouns kill this
WEIGHT_INVALID_CHAR_BN = 0.15
WEIGHT_REGEX_VALIDATION_BN = 0.08
WEIGHT_STRUCTURAL_BN = 0.07

# Legacy aliases (for any old code still using the un-suffixed names)
WEIGHT_OCR_CONFIDENCE = WEIGHT_OCR_CONFIDENCE_EN
WEIGHT_UNICODE_RATIO = WEIGHT_UNICODE_RATIO_EN
WEIGHT_DICTIONARY_MATCH = WEIGHT_DICTIONARY_MATCH_EN
WEIGHT_INVALID_CHAR = WEIGHT_INVALID_CHAR_EN
WEIGHT_REGEX_VALIDATION = WEIGHT_REGEX_VALIDATION_EN
WEIGHT_STRUCTURAL = WEIGHT_STRUCTURAL_EN

# ── Confidence Thresholds ──────────────────────────────────────────────────
HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.80
BANGLA_HIGH_CONFIDENCE = 0.82
BANGLA_MEDIUM_CONFIDENCE = 0.82  # kept for reference only

# LLM fallback trigger thresholds — these are used by needs_api_fallback()
# BUG FIX: was using BANGLA_MEDIUM_CONFIDENCE=0.85 → triggered on ALL pages.
# At 0.62 it only triggers on genuinely poor OCR pages.
API_FALLBACK_THRESHOLD_BANGLA = 0.62
API_FALLBACK_THRESHOLD_ENGLISH = 0.55

# LLM confidence floor — applied after Ollama/Gemini processes a Bangla page.
# Prevents the dictionary penalty from misrepresenting correct LLM output.
LLM_BANGLA_CONFIDENCE_FLOOR = 0.86

# ── Performance (M4 16 GB tuning) ─────────────────────────────────────────
# MEMORY LIMIT: 2 EasyOCR threads × ~1.5 GB = ~3 GB for workers.
# Plus ~2 GB main process. Total ~5 GB. Safe on 16 GB.
MAX_WORKERS = 2
PAGE_BATCH_SIZE = 10

# Bangla-direct LLM path: if a scanned page's quick Bangla estimate exceeds
# this ratio AND Ollama is running, skip EasyOCR and go directly to Ollama.
# Saves 3-8s per page on gazette/government docs (EasyOCR always gets
# superseded by Ollama on Bangla pages anyway).
BANGLA_DIRECT_LLM_THRESHOLD = 0.40

SKIP_LOCAL_OCR_ABOVE_PIXELS = 3_000_000
MAX_IMAGE_DIMENSION = 1024
FAST_MODE = os.getenv("FAST_MODE", "false").lower() == "true"
FAST_MODE_BANGLA = os.getenv("FAST_MODE_BANGLA", "true").lower() == "true"

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = True

# ── Runtime Status ─────────────────────────────────────────────────────────
_runtime_status: dict = {
    "gemini_available": None,
    "ollama_available": None,
    "ollama_model": None,
    "easyocr_available": None,
}


def get_status() -> dict:
    return dict(_runtime_status)


def set_status(key: str, value) -> None:
    if key in _runtime_status:
        _runtime_status[key] = value
