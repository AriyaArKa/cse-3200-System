"""
Configuration module for Smart OCR System.
All tunable parameters in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------
# Base Directories
# -----------------------------------
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.resolve()

OUTPUT_IMAGES_DIR = PROJECT_ROOT / "smart_ocr_output" / "output_images"
JSON_OUTPUT_DIR = PROJECT_ROOT / "smart_ocr_output" / "output_jsons"
MERGED_OUTPUT_DIR = PROJECT_ROOT / "smart_ocr_output" / "merged_outputs"
CACHE_DIR = PROJECT_ROOT / "smart_ocr_output" / "cache"

# -----------------------------------
# API Keys
# -----------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# -----------------------------------
# PDF Processing
# -----------------------------------
POPPLER_PATH = r"D:\3-2\system\Release-25.12.0-0\poppler-25.12.0\Library\bin"
MAX_PDF_SIZE_MB = 50
DPI = 300
OUTPUT_FORMAT = "png"

# -----------------------------------
# PaddleOCR Configuration
# -----------------------------------
PADDLE_USE_GPU = False
PADDLE_LANG = "en"  # PaddleOCR base; we handle Bangla via multilingual
PADDLE_BANGLA_LANG = "bengali"  # PaddleOCR Bangla model identifier
PADDLE_DET_MODEL_DIR = None  # Use default
PADDLE_REC_MODEL_DIR = None  # Use default
PADDLE_SHOW_LOG = False

# -----------------------------------
# Language Detection Thresholds
# -----------------------------------
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF
BANGLA_HEAVY_THRESHOLD = 0.6  # >= 60% Bangla chars → Bangla-heavy
ENGLISH_HEAVY_THRESHOLD = 0.6  # >= 60% English chars → English-heavy
MIXED_THRESHOLD = 0.2  # Both > 20% → Mixed

# -----------------------------------
# Confidence Scoring Weights
# -----------------------------------
WEIGHT_OCR_CONFIDENCE = 0.30
WEIGHT_UNICODE_RATIO = 0.15
WEIGHT_DICTIONARY_MATCH = 0.20
WEIGHT_INVALID_CHAR_RATIO = 0.15
WEIGHT_REGEX_VALIDATION = 0.10
WEIGHT_STRUCTURAL_CONSISTENCY = 0.10

# -----------------------------------
# Confidence Thresholds for Routing
# -----------------------------------
HIGH_CONFIDENCE_THRESHOLD = 0.80  # Accept directly
MEDIUM_CONFIDENCE_THRESHOLD = 0.55  # Local correction
# Below MEDIUM → Gemini fallback

# Bangla-specific (stricter)
BANGLA_HIGH_CONFIDENCE = 0.85
BANGLA_MEDIUM_CONFIDENCE = 0.65

# -----------------------------------
# Native Text Extraction
# -----------------------------------
MIN_UNICODE_RATIO = (
    0.5  # Min ratio of valid unicode for native extraction to be accepted
)
MIN_TEXT_LENGTH = 20  # Min chars for a page to be considered having text
NATIVE_TEXT_CONFIDENCE = 0.95  # Confidence assigned to cleanly extracted native text

# -----------------------------------
# Gemini Fallback
# -----------------------------------
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 2.0  # seconds
GEMINI_MAX_TOKENS_PER_BLOCK = 500
GEMINI_CACHE_ENABLED = True

# -----------------------------------
# Processing
# -----------------------------------
MAX_PARALLEL_PAGES = 4
MAX_PARALLEL_BLOCKS = 8
PROCESSING_TIMEOUT = 120  # seconds per page

# -----------------------------------
# Caching
# -----------------------------------
CACHE_ENABLED = True
CACHE_TTL_HOURS = 24
