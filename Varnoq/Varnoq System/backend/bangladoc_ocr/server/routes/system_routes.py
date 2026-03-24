from fastapi import APIRouter
from fastapi.responses import FileResponse

from bangladoc_ocr.fallback.llm_fallback import get_api_stats
from bangladoc_ocr.server.paths import STATIC_DIR

router = APIRouter()

_OCR_PROGRESS = {
    "is_processing": False,
    "current_file": "",
    "current_page": 0,
    "total_pages": 0,
}


@router.get("/")
def serve_ui() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/stats")
def stats() -> dict:
    return get_api_stats()


@router.get("/ocr/progress")
def ocr_progress() -> dict:
    return dict(_OCR_PROGRESS)
