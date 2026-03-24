"""Custom exception hierarchy for Last-Try OCR.
Allows callers to distinguish failure modes without parsing error strings.
"""


class LastTryOCRError(Exception):
    """Base exception for all Last-Try OCR errors."""


class PDFReadError(LastTryOCRError):
    """PDF could not be opened or is corrupt."""


class PageRenderError(LastTryOCRError):
    """A PDF page could not be rendered to an image."""


class OCREngineError(LastTryOCRError):
    """Local OCR engine (EasyOCR) failed to initialize or crashed."""


class CorruptedFontError(LastTryOCRError):
    """Page contains legacy font encoding that cannot be decoded as Unicode."""


class LLMFallbackError(LastTryOCRError):
    """All LLM fallback engines (Ollama + Gemini) failed for a page."""


class CorpusWriteError(LastTryOCRError):
    """Could not write corpus output (parquet / JSONL)."""


class ConfigurationError(LastTryOCRError):
    """Invalid or missing configuration value."""
