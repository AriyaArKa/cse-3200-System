"""Central configuration for BanglaDOC Surya-clean implementation."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent.parent.resolve()
ASSETS_DIR = BASE_DIR / "assets"

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_DELAY = 2.0
GEMINI_TIMEOUT = 45

OLLAMA_ENABLED = True
OLLAMA_MODEL_PRIORITY = [
    "qwen2.5vl:7b",
    "minicpm-v:8b",
    "minicpm-v",
    "llava:13b",
    "llava:7b",
    "llama3.2-vision",
    "moondream2",
    "moondream",
    "bakllava",
]
OLLAMA_MAX_RETRIES = 1
OLLAMA_MIN_IMAGE_EDGE = 896
OLLAMA_MAX_IMAGE_EDGE = 1280
OLLAMA_STATUS_RECHECK_SECONDS = 30

DPI_HIGH = 250
MAX_PDF_SIZE_MB = 100
OUTPUT_FORMAT = "png"

EASYOCR_LANGUAGES = ["bn", "en"]
EASYOCR_BATCH_SIZE = 1
OCR_ENGINE_PRIORITY = ["easyocr"]

SURYA_MIN_TEXT_LEN = 20

BANGLA_UNICODE_START = 0x0980
BANGLA_UNICODE_END = 0x09FF
BANGLA_HEAVY_THRESHOLD = 0.40
SUSPICIOUS_GLYPHS = set("¢¤ØÿçÐ×ÞßðþæŒœ")

WEIGHT_OCR_CONFIDENCE_EN = 0.35
WEIGHT_UNICODE_RATIO_EN = 0.10
WEIGHT_DICTIONARY_MATCH_EN = 0.20
WEIGHT_INVALID_CHAR_EN = 0.15
WEIGHT_REGEX_VALIDATION_EN = 0.10
WEIGHT_STRUCTURAL_EN = 0.10

WEIGHT_OCR_CONFIDENCE_BN = 0.40
WEIGHT_UNICODE_RATIO_BN = 0.25
WEIGHT_DICTIONARY_MATCH_BN = 0.05
WEIGHT_INVALID_CHAR_BN = 0.15
WEIGHT_REGEX_VALIDATION_BN = 0.08
WEIGHT_STRUCTURAL_BN = 0.07

WEIGHT_OCR_CONFIDENCE = WEIGHT_OCR_CONFIDENCE_EN
WEIGHT_UNICODE_RATIO = WEIGHT_UNICODE_RATIO_EN
WEIGHT_DICTIONARY_MATCH = WEIGHT_DICTIONARY_MATCH_EN
WEIGHT_INVALID_CHAR = WEIGHT_INVALID_CHAR_EN
WEIGHT_REGEX_VALIDATION = WEIGHT_REGEX_VALIDATION_EN
WEIGHT_STRUCTURAL = WEIGHT_STRUCTURAL_EN

HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.80
BANGLA_HIGH_CONFIDENCE = 0.82
BANGLA_MEDIUM_CONFIDENCE = 0.82

API_FALLBACK_THRESHOLD_BANGLA = 0.62
API_FALLBACK_THRESHOLD_ENGLISH = 0.55
API_FALLBACK_THRESHOLD_BN = API_FALLBACK_THRESHOLD_BANGLA
API_FALLBACK_THRESHOLD_EN = API_FALLBACK_THRESHOLD_ENGLISH
LLM_BANGLA_CONFIDENCE_FLOOR = 0.86

PAGE_BATCH_SIZE = 10
BANGLA_DIRECT_LLM_THRESHOLD = 0.40
SKIP_LOCAL_OCR_ABOVE_PIXELS = 3_000_000
MAX_IMAGE_DIMENSION = 1024

LOG_TO_FILE = True

# Set by refresh_config()
DATA_DIR: Path
OUTPUT_DIR: Path
OUTPUT_IMAGES_DIR: Path
JSON_OUTPUT_DIR: Path
MERGED_OUTPUT_DIR: Path
TEXT_OUTPUT_DIR: Path
LOG_DIR: Path

GEMINI_API_KEY: str
GEMINI_ENABLED: bool

OLLAMA_BASE_URL: str
OLLAMA_IMAGE_MODEL: str
OLLAMA_TIMEOUT: int

DPI: int
USE_GPU: bool
EASYOCR_USE_GPU: bool

SURYA_ENABLED: bool
SURYA_MIN_BANGLA_RATIO: float
SURYA_DEVANAGARI_REJECT_THRESHOLD: float
OCR_MIN_BANGLA_RATIO: float
OCR_DEVANAGARI_REJECT_THRESHOLD: float
OCR_FLOW_MODE: str

MAX_WORKERS: int
FAST_MODE: bool
FAST_MODE_BANGLA: bool

LOG_LEVEL: str


def refresh_config() -> None:
    """Reload backend/.env and refresh all environment-derived settings.

    Relative DATA_DIR paths are resolved against the project root (bangladoc_surya_clean),
    not the process current working directory, so outputs land in a stable location.

    Call this at the start of each OCR run (CLI / HTTP) so toggles like SURYA_ENABLED
    take effect without restarting a long-lived server.
    """
    global DATA_DIR, OUTPUT_DIR, OUTPUT_IMAGES_DIR, JSON_OUTPUT_DIR, MERGED_OUTPUT_DIR
    global TEXT_OUTPUT_DIR, LOG_DIR
    global GEMINI_API_KEY, GEMINI_ENABLED
    global OLLAMA_BASE_URL, OLLAMA_IMAGE_MODEL, OLLAMA_TIMEOUT
    global DPI, USE_GPU, EASYOCR_USE_GPU
    global SURYA_ENABLED, SURYA_MIN_BANGLA_RATIO, SURYA_DEVANAGARI_REJECT_THRESHOLD
    global OCR_MIN_BANGLA_RATIO, OCR_DEVANAGARI_REJECT_THRESHOLD, OCR_FLOW_MODE
    global MAX_WORKERS, FAST_MODE, FAST_MODE_BANGLA, LOG_LEVEL

    load_dotenv(dotenv_path=PROJECT_ROOT / "backend" / ".env", override=True)

    raw_data = os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))
    p = Path(raw_data)
    DATA_DIR = p.resolve() if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    OUTPUT_DIR = DATA_DIR
    OUTPUT_IMAGES_DIR = OUTPUT_DIR / "output_images"
    JSON_OUTPUT_DIR = OUTPUT_DIR / "output_jsons"
    MERGED_OUTPUT_DIR = OUTPUT_DIR / "merged_outputs"
    TEXT_OUTPUT_DIR = OUTPUT_DIR / "output_texts"
    LOG_DIR = OUTPUT_DIR / "logs"

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "false").lower() == "true"

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_IMAGE_MODEL = os.getenv("OLLAMA_IMAGE_MODEL", "moondream2")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

    DPI = int(os.getenv("DPI", "200"))
    USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
    EASYOCR_USE_GPU = USE_GPU

    SURYA_ENABLED = os.getenv("SURYA_ENABLED", "true").lower() == "true"
    SURYA_MIN_BANGLA_RATIO = float(os.getenv("SURYA_MIN_BANGLA_RATIO", "0.12"))
    SURYA_DEVANAGARI_REJECT_THRESHOLD = float(
        os.getenv("SURYA_DEVANAGARI_REJECT_THRESHOLD", "0.18")
    )
    OCR_MIN_BANGLA_RATIO = float(os.getenv("OCR_MIN_BANGLA_RATIO", "0.10"))
    OCR_DEVANAGARI_REJECT_THRESHOLD = float(
        os.getenv("OCR_DEVANAGARI_REJECT_THRESHOLD", "0.16")
    )
    OCR_FLOW_MODE = "surya_first" if SURYA_ENABLED else "skip_surya"

    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))
    FAST_MODE = os.getenv("FAST_MODE", "false").lower() == "true"
    FAST_MODE_BANGLA = os.getenv("FAST_MODE_BANGLA", "true").lower() == "true"

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


refresh_config()

_runtime_status: dict = {
    "surya_available": None,
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
