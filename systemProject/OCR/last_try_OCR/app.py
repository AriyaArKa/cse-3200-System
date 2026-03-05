"""
FastAPI endpoint for the Last-Try OCR system.
Upload PDFs and get structured JSON output.
"""

import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from . import config
from .pipeline import process_pdf
from .api_fallback import get_api_stats

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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    """Return API usage statistics."""
    return get_api_stats()


@app.post("/ocr")
async def ocr_upload(files: List[UploadFile] = File(...)):
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
            doc_result = process_pdf(tmp_path, use_multiprocessing=True)
            results.append(doc_result.to_dict())

        except Exception as e:
            logger.exception("Failed to process %s", upload_file.filename)
            results.append(
                {
                    "filename": upload_file.filename,
                    "error": str(e),
                }
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return JSONResponse(content={"documents": results})


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
