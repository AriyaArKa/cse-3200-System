"""
FastAPI endpoint for the Last-Try OCR system.
Upload PDFs and get structured JSON output.
"""

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
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .api_fallback import get_api_stats
from .json_builder import rebuild_corpus_from_json_outputs
from .pipeline import process_pdf

# ── Setup logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Last-Try OCR",
    description="Government-grade hybrid OCR system for Bangla + English PDFs",
    version="1.0.0",
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
def serve_ui():
    """Serve the built-in offline web UI."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


_OCR_PROGRESS = {
    "is_processing": False,
    "current_file": "",
    "current_page": 0,
    "total_pages": 0,
}


def _compute_doc_id(filename: str) -> str:
    """Compute doc_id using pipeline-compatible naming logic."""
    stem = Path(filename).stem
    h = hashlib.md5(stem.encode()).hexdigest()[:8]
    return f"{stem}_{h}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    """Return API usage statistics."""
    return get_api_stats()


@app.get("/ocr/progress")
def ocr_progress():
    """Return latest OCR progress for UI polling."""
    return dict(_OCR_PROGRESS)


@app.get("/corpus/stats")
def corpus_stats():
    """Return corpus stats if available, else default empty counters."""
    stats_path = config.OUTPUT_DIR / "corpus" / "corpus_stats.json"
    try:
        if stats_path.exists():
            with open(stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed reading corpus stats: %s", e)
    return {"total_records": 0}


@app.get("/corpus/export")
def corpus_export():
    """Download the corpus parquet export file."""
    parquet_path = config.OUTPUT_DIR / "corpus" / "corpus.parquet"
    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Corpus parquet not found. Process at least one PDF first.",
        )
    return FileResponse(
        path=str(parquet_path),
        media_type="application/octet-stream",
        filename="bangla_ocr_corpus.parquet",
    )


class VerifyPayload(BaseModel):
    """Request payload for marking a page as verified/unverified."""

    doc_id: str
    page_number: int
    verified: bool


@app.post("/corpus/verify")
def corpus_verify(payload: VerifyPayload):
    """Update verified flag in page JSON and rebuild corpus outputs."""
    page_path = (
        config.JSON_OUTPUT_DIR / payload.doc_id / f"page_{payload.page_number}.json"
    )
    if not page_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Page JSON not found for doc_id={payload.doc_id}, page={payload.page_number}",
        )

    try:
        with open(page_path, "r", encoding="utf-8") as f:
            page_json = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read page JSON: {e}")

    page_json["verified"] = bool(payload.verified)

    try:
        with open(page_path, "w", encoding="utf-8") as f:
            json.dump(page_json, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write page JSON: {e}")

    try:
        rebuild_corpus_from_json_outputs()
    except Exception as e:
        logger.warning("Corpus rebuild failed after verify update: %s", e)

    return {
        "ok": True,
        "doc_id": payload.doc_id,
        "page": payload.page_number,
    }


@app.post("/ocr")
async def ocr_upload(
    files: List[UploadFile] = File(...),
    domain: str = Form("unknown"),
):
    """
    Upload one or more PDFs for OCR processing.
    Returns structured JSON for each document.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []

    for upload_file in files:
        if not upload_file.filename.lower().endswith(".pdf"):
            results.append(
                {
                    "filename": upload_file.filename,
                    "error": "Not a PDF file",
                }
            )
            continue

        # Save to temp file
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, upload_file.filename)
        try:
            content = await upload_file.read()

            # Check file size
            size_mb = len(content) / (1024 * 1024)
            if size_mb > config.MAX_PDF_SIZE_MB:
                results.append(
                    {
                        "filename": upload_file.filename,
                        "error": f"File too large: {size_mb:.1f}MB (max {config.MAX_PDF_SIZE_MB}MB)",
                    }
                )
                continue

            with open(tmp_path, "wb") as f:
                f.write(content)

            # Process
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

            doc_result = await asyncio.to_thread(
                process_pdf,
                tmp_path,
                True,
                domain,
                _progress_cb,
            )
            result_dict = doc_result.to_dict()
            result_dict["doc_id"] = doc_id
            results.append(result_dict)

        except Exception as e:
            logger.exception("Failed to process %s", upload_file.filename)
            results.append(
                {
                    "filename": upload_file.filename,
                    "error": str(e),
                }
            )
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

    return JSONResponse(content={"documents": results})


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
