"""Celery tasks for asynchronous OCR processing."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete

from bangladoc_ocr.celery_app import celery_app
from bangladoc_ocr.db.models import Document, DocumentStatus, JobStatus, OCRJob, Page
from bangladoc_ocr.db.session import AsyncSessionLocal
from bangladoc_ocr.pipeline import process_pdf

logger = logging.getLogger(__name__)


async def _run_job(job_id: str, file_path: str, domain: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(OCRJob, job_id)
        if not job:
            logger.error("OCR job not found: %s", job_id)
            return
        document = await db.get(Document, job.document_id)
        if not document:
            job.status = JobStatus.FAILED
            job.error_msg = "Document record not found"
            job.completed_at = datetime.utcnow()
            await db.commit()
            return

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        document.status = DocumentStatus.PROCESSING
        await db.commit()

        try:
            result = process_pdf(Path(file_path), False, domain)
            await db.execute(delete(Page).where(Page.document_id == document.id))
            for page in result.pages:
                db.add(
                    Page(
                        document_id=document.id,
                        page_number=page.page_number,
                        engine=page.extraction.engine,
                        confidence_score=page.extraction.confidence_score,
                        verified=page.verified,
                        full_text=page.full_text,
                    )
                )
            document.total_pages = result.total_pages
            document.status = DocumentStatus.DONE
            job.status = JobStatus.DONE
            job.error_msg = None
        except Exception as exc:
            logger.exception("OCR async job failed: %s", job_id)
            document.status = DocumentStatus.FAILED
            job.status = JobStatus.FAILED
            job.error_msg = str(exc)
        finally:
            job.completed_at = datetime.utcnow()
            await db.commit()


@celery_app.task(name="bangladoc_ocr.tasks.run_ocr_job")
def run_ocr_job(job_id: str, file_path: str, domain: str) -> None:
    asyncio.run(_run_job(job_id, file_path, domain))

