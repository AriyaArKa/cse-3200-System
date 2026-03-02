"""
FastAPI application – the single entry point for the OCR service.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.document_parser import build_document_result
from app.ocr_service import ocr_all_pages
from app.pdf_processor import PDFProcessingError, pdf_to_images, validate_pdf_bytes
from app.schemas import ProcessingResponse
from app.utils import MAX_FILE_SIZE_MB, cleanup_temp_dir, ensure_base_temp_dir, logger

# ─────────────────────────── App initialisation ──────────────────────────

app = FastAPI(
    title="Gemini OCR Document Processor",
    description="Upload a PDF and receive structured OCR results powered by Google Gemini Vision.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    ensure_base_temp_dir()
    logger.info("Gemini OCR service started.")


# ──────────────────────── Health-check endpoint ──────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ──────────────────────── Upload + process PDF ───────────────────────────

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",  # some clients send this
}


@app.post("/upload-pdf", response_model=ProcessingResponse)
async def upload_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """
    Accept a PDF upload, run OCR via Gemini Vision, and return structured data.
    """
    # ── 1. Validate content type ──
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Only PDF is accepted.",
        )

    # ── 2. Read and validate size ──
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.",
        )

    # ── 3. Quick PDF header check ──
    try:
        validate_pdf_bytes(contents)
    except PDFProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── 4. Write to temp file ──
    tmp_pdf = Path(tempfile.mktemp(suffix=".pdf"))
    tmp_pdf.write_bytes(contents)

    job_dir: Path | None = None
    try:
        # ── 5. PDF → images ──
        logger.info("Converting PDF (%s) to images …", file.filename)
        image_paths, job_dir = await pdf_to_images(tmp_pdf)
        logger.info("Converted %d page(s).", len(image_paths))

        # ── 6. OCR all pages via Gemini ──
        logger.info("Starting Gemini OCR for %d page(s) …", len(image_paths))
        raw_results = await ocr_all_pages(image_paths)

        # ── 7. Post-processing ──
        document, flags = build_document_result(raw_results)

        response = ProcessingResponse(
            success=True,
            data=document,
            validation_flags=flags,
        )

        logger.info(
            "Processing complete: %d pages, type=%s, flags=%d",
            document.total_pages,
            document.document_type,
            len(flags),
        )

        return JSONResponse(content=response.model_dump(), status_code=200)

    except PDFProcessingError as exc:
        logger.error("PDF processing error: %s", exc)
        return JSONResponse(
            content=ProcessingResponse(success=False, error=str(exc)).model_dump(),
            status_code=422,
        )

    except Exception as exc:
        logger.exception("Unexpected error during processing.")
        return JSONResponse(
            content=ProcessingResponse(
                success=False, error=f"Internal error: {exc}"
            ).model_dump(),
            status_code=500,
        )

    finally:
        # ── 8. Clean up temp files ──
        if tmp_pdf.exists():
            tmp_pdf.unlink(missing_ok=True)
        if job_dir:
            cleanup_temp_dir(job_dir)


# ─────────────────────────── Dev entry point ─────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
