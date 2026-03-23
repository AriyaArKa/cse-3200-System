"""FastAPI server for BanglaDOC Surya-clean implementation."""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bangladoc_ocr import config
from bangladoc_ocr.auth import (
    create_access_token,
    find_user_by_email,
    get_current_user,
    hash_password,
    verify_password,
)
from bangladoc_ocr.celery_app import celery_app
from bangladoc_ocr.core.ocr_engine import _init_easyocr
from bangladoc_ocr.core.surya_engine import load as load_surya
from bangladoc_ocr.db.base import Base
from bangladoc_ocr.db.models import Document, DocumentStatus, JobStatus, OCRJob, User
from bangladoc_ocr.db.session import engine, get_db
from bangladoc_ocr.fallback.llm_fallback import get_api_stats
from bangladoc_ocr.output.json_builder import (
    find_page_json_path,
    load_document_json,
    rebuild_corpus_from_json_outputs,
    to_json_compatible,
)
from bangladoc_ocr.schemas import (
    LoginPayload,
    OCRJobResponse,
    RegisterPayload,
    TokenResponse,
    UserResponse,
)

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

_static_dir = Path(__file__).resolve().parent.parent / "static"
_upload_dir = config.OUTPUT_DIR / "uploads"

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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _upload_dir.mkdir(parents=True, exist_ok=True)
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


@app.post("/auth/register", response_model=UserResponse)
async def auth_register(payload: RegisterPayload, db: AsyncSession = Depends(get_db)) -> UserResponse:
    existing = await find_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email.lower().strip(), hashed_password=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@app.post("/auth/login", response_model=TokenResponse)
async def auth_login(payload: LoginPayload, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await find_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role.value,
    )


@app.get("/auth/me", response_model=UserResponse)
async def auth_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@app.post("/ocr")
@limiter.limit("5/minute")
async def ocr_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    domain: str = Form("unknown"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del request

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results: list[OCRJobResponse] = []
    for upload_file in files:
        if not upload_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Not a PDF file: {upload_file.filename}")

        content = await upload_file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > config.MAX_PDF_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {upload_file.filename} ({size_mb:.1f}MB > {config.MAX_PDF_SIZE_MB}MB)",
            )

        unique_name = f"{uuid.uuid4().hex}_{upload_file.filename}"
        doc_id = Path(unique_name).stem
        file_path = _upload_dir / unique_name
        file_path.write_bytes(content)

        document = Document(
            user_id=current_user.id,
            filename=upload_file.filename,
            doc_id=doc_id,
            status=DocumentStatus.PENDING,
            domain=domain,
            total_pages=0,
        )
        db.add(document)
        await db.flush()

        job = OCRJob(document_id=document.id, status=JobStatus.PENDING)
        db.add(job)
        await db.commit()
        await db.refresh(job)

        async_task = celery_app.send_task(
            "bangladoc_ocr.tasks.run_ocr_job",
            args=[job.id, str(file_path), domain],
        )
        job.celery_task_id = async_task.id
        await db.commit()

        results.append(
            OCRJobResponse(
                job_id=job.id,
                document_id=document.id,
                doc_id=doc_id,
                status=job.status.value,
                celery_task_id=job.celery_task_id,
            )
        )

    return JSONResponse(content=to_json_compatible({"jobs": [r.model_dump() for r in results]}))


@app.get("/jobs/{job_id}")
async def job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(OCRJob, Document)
        .join(Document, OCRJob.document_id == Document.id)
        .where(OCRJob.id == job_id, Document.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job, document = row
    return {
        "job_id": job.id,
        "status": job.status.value,
        "error_msg": job.error_msg,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "document": {
            "id": document.id,
            "doc_id": document.doc_id,
            "filename": document.filename,
            "status": document.status.value,
            "total_pages": document.total_pages,
        },
    }


@app.get("/documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return {
        "documents": [
            {
                "id": d.id,
                "doc_id": d.doc_id,
                "filename": d.filename,
                "status": d.status.value,
                "domain": d.domain,
                "total_pages": d.total_pages,
                "created_at": d.created_at,
            }
            for d in docs
        ]
    }


@app.get("/documents/{doc_id}/report")
async def get_document_report(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await db.execute(
        select(Document).where(Document.doc_id == doc_id, Document.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    payload = load_document_json(doc_id)
    if payload is None:
        if document.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
            raise HTTPException(status_code=409, detail="Report not ready yet")
        raise HTTPException(status_code=404, detail="Report JSON not found")

    return JSONResponse(content=to_json_compatible(payload))


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
