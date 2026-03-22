"""Shared mutable state for fallback engines."""

API_STATS = {
    "gemini_calls": 0,
    "gemini_tokens": 0,
    "gemini_errors": 0,
    "ollama_calls": 0,
    "ollama_errors": 0,
    "total_calls": 0,
    "total_tokens": 0,
    "errors": 0,
    "last_engine_used": None,
}

SERVICE_STATUS = {
    "gemini_available": None,
    "gemini_error": None,
    "ollama_available": None,
    "ollama_model": None,
    "ollama_error": None,
    "ollama_last_checked": 0.0,
}
