"""FastAPI server for BanglaDOC Surya-clean implementation."""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bangladoc_ocr import config
from bangladoc_ocr.core.ocr_engine import _init_easyocr
from bangladoc_ocr.core.surya_engine import load as load_surya
from bangladoc_ocr.exceptions import LLMFallbackError, PDFReadError
from bangladoc_ocr.fallback.llm_fallback import get_api_stats
from bangladoc_ocr.output.json_builder import (
    document_engine_tag,
    find_page_json_path,
    rebuild_corpus_from_json_outputs,
    to_json_compatible,
)
from bangladoc_ocr.pipeline import process_pdf

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BanglaDOC Surya Clean",
    description="Surya-first Bangla + English OCR with clean fallback chain",
    version="1.0.0",
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_processing_lock = asyncio.Semaphore(1)
_static_dir = Path(__file__).resolve().parent.parent / "static"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.on_event("startup")
async def warmup() -> None:
    """Warm OCR engines during startup."""
    config.refresh_config()
    logger.info("Warming up OCR engines")
    await asyncio.to_thread(_init_easyocr)
    if config.SURYA_ENABLED:
        await asyncio.to_thread(load_surya)
    logger.info("Warmup done")


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse(str(_static_dir / "index.html"))


_OCR_PROGRESS = {
    "is_processing": False,
    "current_file": "",
    "current_page": 0,
    "total_pages": 0,
}
_progress_lock = asyncio.Lock()


async def _update_progress(**kwargs) -> None:
    async with _progress_lock:
        _OCR_PROGRESS.update(kwargs)


def _compute_doc_id(filename: str) -> str:
    stem = Path(filename).stem
    digest = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/corpus/stats")
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


@app.get("/stats")
def stats() -> dict:
    return get_api_stats()


@app.get("/ocr/progress")
def ocr_progress() -> dict:
    return dict(_OCR_PROGRESS)


@app.get("/corpus/export")
def corpus_export() -> FileResponse:
    parquet_path = config.OUTPUT_DIR / "corpus" / "corpus.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail="Corpus parquet not found")

    return FileResponse(
        path=str(parquet_path),
        media_type="application/octet-stream",
        filename="bangladoc_corpus.parquet",
    )


class VerifyPayload(BaseModel):
    doc_id: str
    page_number: int
    verified: bool


@app.post("/corpus/verify")
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


@app.post("/ocr")
@limiter.limit("5/minute")
async def ocr_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    domain: str = Form("unknown"),
):
    del request

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []
    async with _processing_lock:
        for upload_file in files:
            if not upload_file.filename.lower().endswith(".pdf"):
                results.append({"filename": upload_file.filename, "error": "Not a PDF file"})
                continue

            temp_dir = tempfile.mkdtemp()
            temp_pdf = os.path.join(temp_dir, upload_file.filename)

            try:
                content = await upload_file.read()
                size_mb = len(content) / (1024 * 1024)
                if size_mb > config.MAX_PDF_SIZE_MB:
                    results.append(
                        {
                            "filename": upload_file.filename,
                            "error": f"File too large: {size_mb:.1f}MB (max {config.MAX_PDF_SIZE_MB}MB)",
                        }
                    )
                    continue

                with open(temp_pdf, "wb") as handle:
                    handle.write(content)

                doc_id = _compute_doc_id(upload_file.filename)
                await _update_progress(
                    is_processing=True,
                    current_file=upload_file.filename,
                    current_page=0,
                    total_pages=0,
                )

                loop = asyncio.get_running_loop()

                def _progress_cb(current_page: int, total_pages: int) -> None:
                    future = asyncio.run_coroutine_threadsafe(
                        _update_progress(
                            is_processing=True,
                            current_file=upload_file.filename,
                            current_page=current_page,
                            total_pages=total_pages,
                        ),
                        loop,
                    )
                    try:
                        future.result(timeout=1)
                    except Exception:
                        pass

                doc_result = await asyncio.to_thread(process_pdf, temp_pdf, False, domain, _progress_cb)
                payload = doc_result.to_dict()
                payload["doc_id"] = doc_id
                tag = document_engine_tag(doc_result.pages)
                payload["document"]["output_engine_tag"] = tag
                results.append(to_json_compatible(payload))
            except PDFReadError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except LLMFallbackError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except Exception as exc:
                logger.exception("Failed to process %s", upload_file.filename)
                results.append({"filename": upload_file.filename, "error": str(exc)})
            finally:
                await _update_progress(
                    is_processing=False,
                    current_file="",
                    current_page=0,
                    total_pages=0,
                )
                shutil.rmtree(temp_dir, ignore_errors=True)

    return JSONResponse(content=to_json_compatible({"documents": results}))


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
