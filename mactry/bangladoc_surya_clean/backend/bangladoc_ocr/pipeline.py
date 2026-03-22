"""Compatibility wrapper that exposes process_pdf from modular pipeline tasks."""

from bangladoc_ocr.pipeline_tasks.document_processor import process_pdf

__all__ = ["process_pdf"]
