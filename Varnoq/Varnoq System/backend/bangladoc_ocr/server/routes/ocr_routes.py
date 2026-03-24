import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bangladoc_ocr import config
from bangladoc_ocr.auth import get_current_user
from bangladoc_ocr.celery_app import celery_app
from bangladoc_ocr.db.models import Document, DocumentStatus, JobStatus, OCRJob, User
from bangladoc_ocr.db.session import get_db
from bangladoc_ocr.output.json_builder import to_json_compatible
from bangladoc_ocr.schemas import OCRJobResponse
from bangladoc_ocr.server.paths import UPLOAD_DIR
from bangladoc_ocr.server.rate_limit import limiter

router = APIRouter()


@router.post("/ocr")
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
        file_path = UPLOAD_DIR / unique_name
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


@router.get("/jobs/{job_id}")
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
