"""Pipeline task modules for small, debuggable OCR steps."""

from .document_processor import process_pdf

__all__ = ["process_pdf"]
