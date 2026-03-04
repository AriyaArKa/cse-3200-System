"""
Configuration module for PerfectOCR System.
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

OUTPUT_IMAGES_DIR = PROJECT_ROOT / "perfect_ocr_output" / "output_images"
JSON_OUTPUT_DIR = PROJECT_ROOT / "perfect_ocr_output" / "output_jsons"
MERGED_OUTPUT_DIR = PROJECT_ROOT / "perfect_ocr_output" / "merged_outputs"
CACHE_DIR = PROJECT_ROOT / "perfect_ocr_output" / "cache"

# -----------------------------------
# API Keys
# -----------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Model names
GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o"

# OpenAI base URL (for GitHub Copilot or Azure, leave empty for default)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# -----------------------------------
# PDF Processing
# -----------------------------------
POPPLER_PATH = os.getenv(
    "POPPLER_PATH",
    r"D:\3-2\system\Release-25.12.0-0\poppler-25.12.0\Library\bin",
)
MAX_PDF_SIZE_MB = 50
DPI = 250  # Higher DPI for better handwriting/numeral recognition
OUTPUT_FORMAT = "png"

# -----------------------------------
# OCR Strategy
# -----------------------------------
# "gpt4o_primary"  → GPT-4o first, Gemini fallback
# "gemini_primary" → Gemini first, GPT-4o fallback
# "dual"           → Both models, merge results
# "gpt4o_only"     → GPT-4o only
# "gemini_only"    → Gemini only
DEFAULT_STRATEGY = "gemini_primary"

# -----------------------------------
# Gemini Settings
# -----------------------------------
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 2.0  # seconds
GEMINI_MAX_TOKENS = 8000

# -----------------------------------
# OpenAI / GPT-4o Settings
# -----------------------------------
OPENAI_MAX_RETRIES = 3
OPENAI_RETRY_DELAY = 2.0
OPENAI_MAX_TOKENS = 8000

# -----------------------------------
# Bangla Correction
# -----------------------------------
ENABLE_BANGLA_CORRECTION = True
CORRECTION_MODEL = (
    "gemini-2.5-flash"  # Model for post-correction pass (Gemini = fewer GPT calls)
)

# -----------------------------------
# Caching
# -----------------------------------
CACHE_ENABLED = True
CACHE_TTL_HOURS = 24

# -----------------------------------
# Language Detection
# -----------------------------------
BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF

# -----------------------------------
# Processing
# -----------------------------------
PROCESSING_TIMEOUT = 120  # seconds per page
