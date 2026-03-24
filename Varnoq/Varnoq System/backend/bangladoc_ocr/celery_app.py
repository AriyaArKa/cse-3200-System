"""Celery app configuration."""

from celery import Celery

from bangladoc_ocr import config

celery_app = Celery(
    "bangladoc_ocr",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
celery_app.autodiscover_tasks(["bangladoc_ocr"])

