import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from bangladoc_ocr import config
from bangladoc_ocr.output.json_builder import (
    find_page_json_path,
    rebuild_corpus_from_json_outputs,
    to_json_compatible,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class VerifyPayload(BaseModel):
    doc_id: str
    page_number: int
    verified: bool


@router.get("/corpus/stats")
def corpus_stats() -> dict:
    stats_path = config.OUTPUT_DIR / "corpus" / "corpus_stats.json"
    try:
        if stats_path.exists():
            return json.loads(stats_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading corpus stats: %s", exc)

    return {
        "total_records": 0,
        "by_domain": {},
        "by_tier": {},
        "by_engine": {},
        "avg_confidence": 0.0,
        "total_words": 0,
        "total_chars": 0,
    }


@router.get("/corpus/export")
def corpus_export() -> FileResponse:
    parquet_path = config.OUTPUT_DIR / "corpus" / "corpus.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail="Corpus parquet not found")

    return FileResponse(
        path=str(parquet_path),
        media_type="application/octet-stream",
        filename="bangladoc_corpus.parquet",
    )


@router.post("/corpus/verify")
def corpus_verify(payload: VerifyPayload) -> dict:
    page_path = find_page_json_path(payload.doc_id, payload.page_number)
    if page_path is None or not page_path.exists():
        raise HTTPException(status_code=404, detail="Page JSON not found")

    try:
        page_json = json.loads(page_path.read_text(encoding="utf-8"))
        page_json["verified"] = bool(payload.verified)
        page_path.write_text(
            json.dumps(to_json_compatible(page_json), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rebuild_corpus_from_json_outputs()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verify update failed: {exc}") from exc

    return {"ok": True, "doc_id": payload.doc_id, "page": payload.page_number}
