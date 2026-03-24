"""Document-level orchestration for OCR pipeline."""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from bangladoc_ocr import config
from bangladoc_ocr.core.surya_engine import load as surya_load
from bangladoc_ocr.core.pdf_router import open_pdf
from bangladoc_ocr.models import DocumentResult
from bangladoc_ocr.output.json_builder import save_document_json

from .helpers import build_doc_id, detect_languages
from .page_processor import process_page

ProgressCB = Callable[[int, int], None]

logger = logging.getLogger(__name__)


def process_pdf(
    pdf_path: str | Path,
    use_multiprocessing: bool = False,
    domain: str = "general",
    progress_callback: Optional[ProgressCB] = None,
) -> DocumentResult:
    """Process a PDF end-to-end and return DocumentResult."""
    del use_multiprocessing

    config.refresh_config()

    if config.SURYA_ENABLED:
        surya_load()

    pdf_path = Path(pdf_path)
    doc_id = build_doc_id(pdf_path)
    start = time.time()

    document = open_pdf(pdf_path)
    total_pages = len(document)
    pages = []

    logger.info("Processing %s (%d pages)", pdf_path.name, total_pages)

    for index in range(total_pages):
        page_number = index + 1
        if progress_callback:
            try:
                progress_callback(page_number, total_pages)
            except Exception:
                pass

        page_result = process_page(document[index], page_number, str(pdf_path), doc_id, domain)
        pages.append(page_result)

    document.close()

    confidence_values = [page.extraction.confidence_score for page in pages]
    overall_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0

    result = DocumentResult(
        source=pdf_path.name,
        total_pages=total_pages,
        language_detected=detect_languages(pages),
        overall_confidence=overall_confidence,
        pages=pages,
        processing_time_ms=(time.time() - start) * 1000,
        pages_processed_locally=sum(
            1 for page in pages if page.extraction.engine in ("surya", "easyocr", "PyMuPDF")
        ),
        pages_sent_to_api=sum(
            1
            for page in pages
            if page.extraction.engine.startswith("ollama") or page.extraction.engine == "gemini"
        ),
    )

    save_document_json(result, doc_id)
    return result
