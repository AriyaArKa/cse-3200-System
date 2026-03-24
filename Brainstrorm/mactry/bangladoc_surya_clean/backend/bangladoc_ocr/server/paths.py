import json
from pathlib import Path

from bangladoc_ocr import config

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
UPLOAD_DIR = config.OUTPUT_DIR / "uploads"
PROGRESS_DIR = config.OUTPUT_DIR / "job_progress"


def read_doc_progress(doc_id: str) -> dict | None:
    path = PROGRESS_DIR / f"{doc_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_doc_progress(doc_id: str, payload: dict) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (PROGRESS_DIR / f"{doc_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
