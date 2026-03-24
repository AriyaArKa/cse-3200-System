import logging
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bangladoc_ocr import config
from bangladoc_ocr.auth import get_current_user
from bangladoc_ocr.celery_app import celery_app
from bangladoc_ocr.db.models import ChatSession, Chunk, Document, DocumentStatus, JobStatus, OCRJob, Page, User
from bangladoc_ocr.db.session import get_db
from bangladoc_ocr.output.json_builder import load_document_json, to_json_compatible
from bangladoc_ocr.server.paths import PROGRESS_DIR, UPLOAD_DIR, read_doc_progress, write_doc_progress

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    items = []
    for d in docs:
        progress_percent = 0
        progress_status = None
        progress = read_doc_progress(d.doc_id)
        if d.status == DocumentStatus.DONE:
            progress_percent = 100
            progress_status = "done"
        elif progress:
            current_page = int(progress.get("current_page", 0) or 0)
            total_pages = int(progress.get("total_pages", 0) or 0)
            if total_pages > 0:
                progress_percent = max(0, min(100, int(round((current_page / total_pages) * 100))))
            progress_status = progress.get("status")

        items.append(
            {
                "id": d.id,
                "doc_id": d.doc_id,
                "filename": d.filename,
                "status": d.status.value,
                "domain": d.domain,
                "total_pages": d.total_pages,
                "progress_percent": progress_percent,
                "progress_status": progress_status,
                "created_at": d.created_at,
            }
        )

    return {"documents": items}


@router.post("/documents/{doc_id}/cancel")
async def cancel_document_processing(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.doc_id == doc_id, Document.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs_result = await db.execute(select(OCRJob).where(OCRJob.document_id == document.id))
    jobs = jobs_result.scalars().all()
    active_jobs = [j for j in jobs if j.status in (JobStatus.PENDING, JobStatus.PROCESSING)]
    if not active_jobs:
        raise HTTPException(status_code=409, detail="No active processing job for this document")

    for job in active_jobs:
        if job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception:
                logger.warning("Failed to revoke celery task %s", job.celery_task_id)
        job.status = JobStatus.FAILED
        job.error_msg = "Canceled by user"
        job.completed_at = datetime.utcnow()

    document.status = DocumentStatus.FAILED
    await db.commit()

    write_doc_progress(
        doc_id,
        {
            "doc_id": doc_id,
            "current_page": 0,
            "total_pages": document.total_pages,
            "status": "canceled",
            "message": "Canceled by user",
        },
    )

    return {"ok": True, "doc_id": doc_id, "message": "Processing canceled"}


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.doc_id == doc_id, Document.user_id == current_user.id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs_result = await db.execute(select(OCRJob).where(OCRJob.document_id == document.id))
    jobs = jobs_result.scalars().all()
    for job in jobs:
        if job.status in (JobStatus.PENDING, JobStatus.PROCESSING) and job.celery_task_id:
            try:
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception:
                logger.warning("Failed to revoke celery task %s", job.celery_task_id)

    await db.execute(delete(Page).where(Page.document_id == document.id))
    await db.execute(delete(OCRJob).where(OCRJob.document_id == document.id))
    await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
    await db.execute(delete(ChatSession).where(ChatSession.document_id == document.id))
    await db.delete(document)
    await db.commit()

    json_dir = config.JSON_OUTPUT_DIR / doc_id
    image_dir = config.OUTPUT_IMAGES_DIR / doc_id
    if json_dir.exists():
        shutil.rmtree(json_dir, ignore_errors=True)
    if image_dir.exists():
        shutil.rmtree(image_dir, ignore_errors=True)

    for path in config.MERGED_OUTPUT_DIR.glob(f"{doc_id}_*.json"):
        path.unlink(missing_ok=True)
    (config.MERGED_OUTPUT_DIR / f"{doc_id}.json").unlink(missing_ok=True)

    for path in config.TEXT_OUTPUT_DIR.glob(f"{doc_id}_*.txt"):
        path.unlink(missing_ok=True)
    (config.TEXT_OUTPUT_DIR / f"{doc_id}.txt").unlink(missing_ok=True)

    (PROGRESS_DIR / f"{doc_id}.json").unlink(missing_ok=True)

    for path in UPLOAD_DIR.glob("*.pdf"):
        if path.stem == doc_id:
            path.unlink(missing_ok=True)

    return {"ok": True, "doc_id": doc_id, "message": "Document and outputs deleted"}


@router.get("/documents/{doc_id}/report")
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
