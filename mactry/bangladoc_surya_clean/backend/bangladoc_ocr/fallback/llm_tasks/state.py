"""Shared mutable state for fallback engines."""

import threading

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

_stats_lock = threading.Lock()


def increment_stat(key: str, amount: int = 1):
    with _stats_lock:
        API_STATS[key] = API_STATS.get(key, 0) + amount


def set_stat(key: str, value):
    with _stats_lock:
        API_STATS[key] = value


def get_stat(key: str, default=None):
    with _stats_lock:
        return API_STATS.get(key, default)


def get_api_stats_snapshot() -> dict:
    with _stats_lock:
        return dict(API_STATS)


def set_service_status(key: str, value):
    with _stats_lock:
        SERVICE_STATUS[key] = value


def get_service_status(key: str, default=None):
    with _stats_lock:
        return SERVICE_STATUS.get(key, default)


def get_service_status_snapshot() -> dict:
    with _stats_lock:
        return dict(SERVICE_STATUS)
