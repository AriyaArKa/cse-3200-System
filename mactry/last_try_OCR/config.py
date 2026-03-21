"""
Central configuration for Last-Try OCR.
Optimized for: Mac Mini M4 · 16 GB RAM · Python 3.14 · EasyOCR only
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# -- Directories ------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.resolve()
OUTPUT_DIR = PROJECT_ROOT / "last_try_output"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "output_images"
JSON_OUTPUT_DIR = OUTPUT_DIR / "output_jsons"
MERGED_OUTPUT_DIR = OUTPUT_DIR / "merged_outputs"
LOG_DIR = OUTPUT_DIR / "logs"

# -- Gemini (cloud fallback, free tier) ------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_DELAY = 2.0
GEMINI_TIMEOUT = 45

# -- Ollama (local LLM, primary fallback) ----------------------------------
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

# -- PDF Processing ---------------------------------------------------------
DPI = 180
DPI_HIGH = 250
MAX_PDF_SIZE_MB = 100
OUTPUT_FORMAT = "png"

# -- OCR Engine (EasyOCR only) ---------------------------------------------
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
EASYOCR_USE_GPU = USE_GPU
EASYOCR_LANGUAGES = ["bn", "en"]
EASYOCR_BATCH_SIZE = 1
OCR_ENGINE_PRIORITY = ["easyocr"]

# -- Unicode / Language Detection ------------------------------------------
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF
BANGLA_HEAVY_THRESHOLD = 0.40
SUSPICIOUS_GLYPHS = set("¢¤ØÿçÐ×ÞßðþæŒœ")

# -- Confidence Scoring Weights --------------------------------------------
WEIGHT_OCR_CONFIDENCE = 0.30
WEIGHT_UNICODE_RATIO = 0.15
WEIGHT_DICTIONARY_MATCH = 0.20
WEIGHT_INVALID_CHAR = 0.15
WEIGHT_REGEX_VALIDATION = 0.10
WEIGHT_STRUCTURAL = 0.10

# -- Confidence Thresholds --------------------------------------------------
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.80
BANGLA_HIGH_CONFIDENCE = 0.85
BANGLA_MEDIUM_CONFIDENCE = 0.85
API_FALLBACK_THRESHOLD_ENGLISH = 0.55
API_FALLBACK_THRESHOLD_BANGLA = 0.65

# -- Performance (M4 16 GB tuning) -----------------------------------------
MAX_WORKERS = 2
PAGE_BATCH_SIZE = 10
SKIP_LOCAL_OCR_ABOVE_PIXELS = 3_000_000
MAX_IMAGE_DIMENSION = 1024
FAST_MODE = os.getenv("FAST_MODE", "false").lower() == "true"
FAST_MODE_BANGLA = os.getenv("FAST_MODE_BANGLA", "true").lower() == "true"

# -- Logging ----------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = True

# -- Runtime Status ---------------------------------------------------------
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
