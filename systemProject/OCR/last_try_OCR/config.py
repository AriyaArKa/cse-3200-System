"""
Central configuration for Last-Try OCR system.
All configurable variables are centralized here for easy modification.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════════════
# DIRECTORIES
# ══════════════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.resolve()

OUTPUT_DIR = PROJECT_ROOT / "last_try_output"
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "output_images"
JSON_OUTPUT_DIR = OUTPUT_DIR / "output_jsons"
MERGED_OUTPUT_DIR = OUTPUT_DIR / "merged_outputs"
LOG_DIR = OUTPUT_DIR / "logs"

# ══════════════════════════════════════════════════════════════════════
# GEMINI API SETTINGS
# ══════════════════════════════════════════════════════════════════════
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = (
    "gemini-2.0-flash"  # Options: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro
)
GEMINI_MAX_RETRIES = 2  # Reduced for faster fallback to local LLM
GEMINI_RETRY_DELAY = 1.0  # Seconds between retries
GEMINI_TIMEOUT = 30  # Timeout in seconds
GEMINI_ENABLED = bool(GEMINI_API_KEY)  # Auto-detect if Gemini is available

# ══════════════════════════════════════════════════════════════════════
# LOCAL LLM SETTINGS (Ollama fallback)
# ══════════════════════════════════════════════════════════════════════
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_ENABLED = True  # Set False to disable local LLM fallback

# Ordered list of vision-capable models to try (first available will be used)
# Only vision models can do OCR - text-only models are skipped
OLLAMA_MODEL_PRIORITY = [
    "llava:7b",  # Best for OCR - vision model
    "llava:13b",  # Higher quality vision
    "llama3.2-vision",  # Good for multilingual
    "minicpm-v",  # Fast vision model
    "moondream",  # Lightweight vision
    "bakllava",  # Alternative vision model
]
OLLAMA_TIMEOUT = 45  # Timeout for local LLM calls (reduced for speed)
OLLAMA_MAX_RETRIES = 1  # Local LLM retries (keep low - it's the fallback)

# ══════════════════════════════════════════════════════════════════════
# PDF PROCESSING
# ══════════════════════════════════════════════════════════════════════
DPI = 200  # Render DPI for OCR (200 = good balance of speed/quality)
DPI_HIGH = 300  # High quality DPI (for critical documents)
DPI_LOW = 150  # Fast preview DPI
MAX_PDF_SIZE_MB = 100
OUTPUT_FORMAT = "png"

# ══════════════════════════════════════════════════════════════════════
# OCR ENGINE SETTINGS
# ══════════════════════════════════════════════════════════════════════
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
PADDLE_USE_GPU = USE_GPU
EASYOCR_USE_GPU = USE_GPU

# OCR engine priority (first available will be used)
# PaddleOCR is faster for Bangla; EasyOCR as fallback
OCR_ENGINE_PRIORITY = ["paddleocr", "easyocr"]  # Order of preference

# PaddleOCR specific
PADDLE_DET_DB_THRESH = 0.3  # Detection threshold
PADDLE_DET_BOX_THRESH = 0.5  # Box threshold
PADDLE_REC_BATCH_NUM = 6  # Batch recognition for speed

# EasyOCR specific
EASYOCR_LANGUAGES = ["bn", "en"]  # Languages to load
EASYOCR_BATCH_SIZE = 1  # Batch size for OCR (1 = lowest memory)

# ══════════════════════════════════════════════════════════════════════
# UNICODE / LANGUAGE DETECTION
# ══════════════════════════════════════════════════════════════════════
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF
BANGLA_HEAVY_THRESHOLD = 0.40  # ≥40% Bangla chars → Bangla-heavy
SUSPICIOUS_GLYPHS = set("¢¤ØÿçÐ×ÞßðþæŒœ")

# ══════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING WEIGHTS (must sum to 1.0)
# ══════════════════════════════════════════════════════════════════════
WEIGHT_OCR_CONFIDENCE = 0.30
WEIGHT_UNICODE_RATIO = 0.15
WEIGHT_DICTIONARY_MATCH = 0.20
WEIGHT_INVALID_CHAR = 0.15
WEIGHT_REGEX_VALIDATION = 0.10
WEIGHT_STRUCTURAL = 0.10

# ══════════════════════════════════════════════════════════════════════
# CONFIDENCE THRESHOLDS
# ══════════════════════════════════════════════════════════════════════
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.55
BANGLA_HIGH_CONFIDENCE = 0.85
BANGLA_MEDIUM_CONFIDENCE = 0.65

# Fallback trigger thresholds
API_FALLBACK_THRESHOLD_ENGLISH = 0.55  # Below this → try API/LLM
API_FALLBACK_THRESHOLD_BANGLA = 0.65  # Bangla needs higher threshold

# ══════════════════════════════════════════════════════════════════════
# SPEED OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════
# Skip EasyOCR for large images (use Gemini/LLM directly)
SKIP_LOCAL_OCR_ABOVE_PIXELS = 2_000_000  # ~1400x1400 pixels
# Maximum image dimension for API calls (resize if larger)
MAX_IMAGE_DIMENSION = 2048
# Enable fast mode (lower DPI, skip some validations)
FAST_MODE = os.getenv("FAST_MODE", "false").lower() == "true"
# Fast mode specifically for Bangla processing (minimal preprocessing)
FAST_MODE_BANGLA = os.getenv("FAST_MODE_BANGLA", "true").lower() == "true"
# Use parallel page processing when available
PARALLEL_PAGE_OCR = True

# ══════════════════════════════════════════════════════════════════════
# MULTIPROCESSING
# ══════════════════════════════════════════════════════════════════════
MAX_WORKERS = min(os.cpu_count() or 4, 8)
# Disable multiprocessing for debugging
DISABLE_MULTIPROCESSING = os.getenv("DISABLE_MP", "false").lower() == "true"

# ══════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = True
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ══════════════════════════════════════════════════════════════════════
# STATUS TRACKING (runtime - do not modify)
# ══════════════════════════════════════════════════════════════════════
_runtime_status = {
    "gemini_available": None,  # Will be set on first call
    "ollama_available": None,
    "ollama_model": None,
    "easyocr_available": None,
    "paddleocr_available": None,
}


def get_status() -> dict:
    """Get current runtime status of all services."""
    return dict(_runtime_status)


def set_status(key: str, value) -> None:
    """Update runtime status."""
    if key in _runtime_status:
        _runtime_status[key] = value
