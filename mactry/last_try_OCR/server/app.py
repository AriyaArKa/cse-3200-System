"""FastAPI app for Last-Try OCR."""

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

from .. import config
from ..core.ocr_engine import _init_easyocr
from ..exceptions import LLMFallbackError, PDFReadError
from ..fallback.llm_fallback import get_api_stats
from ..output.json_builder import rebuild_corpus_from_json_outputs, to_json_compatible
from ..pipeline import process_pdf

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Last-Try OCR",
    description="Government-grade hybrid OCR system for Bangla + English PDFs",
    version="2.0.0",
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_processing_lock = asyncio.Semaphore(1)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.on_event("startup")
async def warmup() -> None:
    """Pre-load EasyOCR model to avoid first-request latency."""
    logger.info("Warming up EasyOCR (loading bn+en models)...")
    await asyncio.to_thread(_init_easyocr)
    logger.info("EasyOCR ready.")


@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


_OCR_PROGRESS = {
    "is_processing": False,
    "current_file": "",
    "current_page": 0,
    "total_pages": 0,
}


def _compute_doc_id(filename: str) -> str:
    stem = Path(filename).stem
    h = hashlib.md5(stem.encode()).hexdigest()[:8]
    return f"{stem}_{h}"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
        filename="bangla_ocr_corpus.parquet",
    )


class VerifyPayload(BaseModel):
    doc_id: str
    page_number: int
    verified: bool


@app.post("/corpus/verify")
def corpus_verify(payload: VerifyPayload) -> dict:
    page_path = config.JSON_OUTPUT_DIR / payload.doc_id / f"page_{payload.page_number}.json"
    if not page_path.exists():
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
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []
    async with _processing_lock:
        for upload_file in files:
            if not upload_file.filename.lower().endswith(".pdf"):
                results.append({"filename": upload_file.filename, "error": "Not a PDF file"})
                continue

            tmp_dir = tempfile.mkdtemp()
            tmp_path = os.path.join(tmp_dir, upload_file.filename)
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

                with open(tmp_path, "wb") as fh:
                    fh.write(content)

                doc_id = _compute_doc_id(upload_file.filename)
                _OCR_PROGRESS.update(
                    {
                        "is_processing": True,
                        "current_file": upload_file.filename,
                        "current_page": 0,
                        "total_pages": 0,
                    }
                )

                def _progress_cb(current_page: int, total_pages: int) -> None:
                    _OCR_PROGRESS.update(
                        {
                            "is_processing": True,
                            "current_file": upload_file.filename,
                            "current_page": current_page,
                            "total_pages": total_pages,
                        }
                    )

                doc_result = await asyncio.to_thread(process_pdf, tmp_path, True, domain, _progress_cb)
                result_dict = doc_result.to_dict()
                result_dict["doc_id"] = doc_id
                results.append(to_json_compatible(result_dict))
            except PDFReadError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except LLMFallbackError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except Exception as exc:
                logger.exception("Failed to process %s", upload_file.filename)
                results.append({"filename": upload_file.filename, "error": str(exc)})
            finally:
                _OCR_PROGRESS.update(
                    {
                        "is_processing": False,
                        "current_file": "",
                        "current_page": 0,
                        "total_pages": 0,
                    }
                )
                shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse(content=to_json_compatible({"documents": results}))


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
