"""Prompt loading for OCR fallback engines."""

from pathlib import Path


def _load_prompt(path: Path, fallback: str) -> str:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


def load_prompts() -> tuple[str, str]:
    base = Path(__file__).resolve().parents[2] / "assets" / "prompts"
    ocr_prompt = _load_prompt(base / "ocr_prompt.txt", "Extract all text from this document image.")
    ollama_prompt = _load_prompt(base / "ollama_prompt.txt", ocr_prompt)
    return ocr_prompt, ollama_prompt
