"""Celery tasks for asynchronous OCR processing."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import delete

from bangladoc_ocr import config
from bangladoc_ocr.celery_app import celery_app
from bangladoc_ocr.db.models import Document, DocumentStatus, JobStatus, OCRJob, Page
from bangladoc_ocr.db.session import AsyncSessionLocal
from bangladoc_ocr.pipeline import process_pdf

logger = logging.getLogger(__name__)

_worker_loop: Optional[asyncio.AbstractEventLoop] = None


def _progress_file(doc_id: str) -> Path:
    progress_dir = config.OUTPUT_DIR / "job_progress"
    progress_dir.mkdir(parents=True, exist_ok=True)
    return progress_dir / f"{doc_id}.json"


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent asyncio loop for this worker process.

    Celery tasks are synchronous entrypoints, but this module uses async DB sessions.
    Recreating a loop for each task can leave pooled asyncpg connections bound to an
    old closed loop, causing cross-loop runtime errors on subsequent jobs.
    """
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


def _write_progress(doc_id: str, current_page: int, total_pages: int, status: str, message: str = "") -> None:
    payload = {
        "doc_id": doc_id,
        "current_page": int(current_page),
        "total_pages": int(total_pages),
        "status": status,
        "message": message,
        "updated_at": datetime.utcnow().isoformat(),
    }
    _progress_file(doc_id).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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

        doc_id = document.doc_id
        _write_progress(doc_id, 0, document.total_pages, "processing")

        try:
            loop = asyncio.get_running_loop()

            async def _update_progress(current_page: int, total_pages: int) -> None:
                if total_pages > 0 and document.total_pages != total_pages:
                    document.total_pages = total_pages
                    await db.commit()
                _write_progress(doc_id, current_page, total_pages, "processing")

            def _progress_cb(current_page: int, total_pages: int) -> None:
                fut = asyncio.run_coroutine_threadsafe(
                    _update_progress(current_page, total_pages),
                    loop,
                )
                try:
                    fut.result(timeout=2)
                except Exception:
                    pass

            result = await asyncio.to_thread(process_pdf, Path(file_path), False, domain, _progress_cb)
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
            _write_progress(doc_id, result.total_pages, result.total_pages, "done")
        except Exception as exc:
            logger.exception("OCR async job failed: %s", job_id)
            document.status = DocumentStatus.FAILED
            job.status = JobStatus.FAILED
            job.error_msg = str(exc)
            _write_progress(doc_id, 0, document.total_pages, "failed", str(exc))
        finally:
            job.completed_at = datetime.utcnow()
            await db.commit()


@celery_app.task(name="bangladoc_ocr.tasks.run_ocr_job")
def run_ocr_job(job_id: str, file_path: str, domain: str) -> None:
    loop = _get_worker_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_job(job_id, file_path, domain))

