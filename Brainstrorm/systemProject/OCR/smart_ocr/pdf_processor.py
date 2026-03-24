"""
Smart PDF Processor Module.
Handles intelligent PDF processing:
  1. Attempts native text extraction first (pdfplumber / PyMuPDF)
  2. Only converts pages to images when native extraction fails
  3. Classifies each page as native_text, ocr, or hybrid
"""

import os
import uuid
import logging
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

import fitz  # PyMuPDF
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image

from . import config

logger = logging.getLogger(__name__)


@dataclass
class PageClassification:
    """Classification of a single PDF page."""

    page_number: int
    has_native_text: bool
    native_text: str
    text_length: int
    unicode_ratio: float  # ratio of valid unicode chars
    needs_ocr: bool
    image_path: Optional[str] = None


class SmartPDFProcessor:
    """
    Intelligently processes PDFs:
    - Tries native text extraction first
    - Only converts to image if native extraction fails
    - Never blindly converts entire PDF to images
    """

    def __init__(self, pdf_path: str, output_images_dir: str = None):
        self.pdf_path = Path(pdf_path)
        self.output_images_dir = Path(output_images_dir or config.OUTPUT_IMAGES_DIR)
        self._validate_pdf()

    def _validate_pdf(self):
        """Validate PDF file."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("File must be a PDF")
        size_mb = self.pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > config.MAX_PDF_SIZE_MB:
            raise ValueError(
                f"PDF exceeds {config.MAX_PDF_SIZE_MB}MB limit ({size_mb:.1f}MB)"
            )
        logger.info(f"PDF validated: {self.pdf_path.name} ({size_mb:.2f} MB)")

    def _calculate_unicode_ratio(self, text: str) -> float:
        """Calculate ratio of valid unicode characters (Bangla + English + common punctuation)."""
        if not text.strip():
            return 0.0

        valid_count = 0
        total = len(text)
        for ch in text:
            cp = ord(ch)
            # Bangla unicode block
            if config.BANGLA_UNICODE_START <= cp <= config.BANGLA_UNICODE_END:
                valid_count += 1
            # ASCII printable (English letters, digits, punctuation)
            elif 0x0020 <= cp <= 0x007E:
                valid_count += 1
            # Common whitespace & formatting
            elif ch in "\n\r\t ":
                valid_count += 1
            # Extended punctuation / common symbols
            elif cp in range(0x2000, 0x206F):  # General punctuation
                valid_count += 1

        return valid_count / total if total > 0 else 0.0

    def _extract_native_text(self, page_num: int) -> Tuple[str, float]:
        """
        Attempt native text extraction using PyMuPDF.
        Returns (text, unicode_ratio).
        """
        try:
            doc = fitz.open(self.pdf_path)
            page = doc.load_page(page_num)
            text = page.get_text("text")
            doc.close()

            unicode_ratio = self._calculate_unicode_ratio(text)
            return text.strip(), unicode_ratio
        except Exception as e:
            logger.warning(f"Native extraction failed for page {page_num + 1}: {e}")
            return "", 0.0

    def _convert_page_to_image(self, page_num: int, run_id: str) -> str:
        """Convert a single page to image. Only called when native extraction fails."""
        self.output_images_dir.mkdir(parents=True, exist_ok=True)

        try:
            images = convert_from_path(
                str(self.pdf_path),
                dpi=config.DPI,
                fmt=config.OUTPUT_FORMAT,
                first_page=page_num + 1,
                last_page=page_num + 1,
                thread_count=2,
                poppler_path=config.POPPLER_PATH if os.name == "nt" else None,
            )

            if images:
                filename = f"page_{page_num + 1}_{run_id}.{config.OUTPUT_FORMAT}"
                img_path = self.output_images_dir / filename
                images[0].save(
                    str(img_path), config.OUTPUT_FORMAT.upper(), optimize=True
                )
                logger.info(f"Page {page_num + 1} → image: {img_path}")
                return str(img_path)
        except Exception as e:
            logger.error(f"Image conversion failed for page {page_num + 1}: {e}")

        return ""

    def classify_pages(self, progress_callback=None) -> List[PageClassification]:
        """
        Classify each page of the PDF:
        - Has native text? → Use it (skip image conversion)
        - No text / bad unicode? → Convert to image for OCR
        """
        try:
            doc = fitz.open(self.pdf_path)
            total_pages = doc.page_count
            doc.close()
        except Exception:
            # Fallback: get page count from poppler
            info = pdfinfo_from_path(
                str(self.pdf_path),
                poppler_path=config.POPPLER_PATH if os.name == "nt" else None,
            )
            total_pages = info["Pages"]

        logger.info(f"Classifying {total_pages} pages...")
        run_id = uuid.uuid4().hex[:8]
        classifications = []

        for page_num in range(total_pages):
            if progress_callback:
                progress_callback(page_num + 1, total_pages, "Classifying pages...")

            # Step 1: Try native text extraction
            native_text, unicode_ratio = self._extract_native_text(page_num)
            text_length = len(native_text)

            has_native = (
                text_length >= config.MIN_TEXT_LENGTH
                and unicode_ratio >= config.MIN_UNICODE_RATIO
            )

            needs_ocr = not has_native
            image_path = None

            # Step 2: Convert to image only if OCR is needed
            if needs_ocr:
                logger.info(
                    f"Page {page_num + 1}: Native extraction insufficient "
                    f"(len={text_length}, unicode_ratio={unicode_ratio:.2f}). Converting to image."
                )
                image_path = self._convert_page_to_image(page_num, run_id)
            else:
                logger.info(
                    f"Page {page_num + 1}: Native text OK "
                    f"(len={text_length}, unicode_ratio={unicode_ratio:.2f}). Skipping image."
                )

            classifications.append(
                PageClassification(
                    page_number=page_num + 1,
                    has_native_text=has_native,
                    native_text=native_text if has_native else "",
                    text_length=text_length,
                    unicode_ratio=unicode_ratio,
                    needs_ocr=needs_ocr,
                    image_path=image_path,
                )
            )

        ocr_count = sum(1 for c in classifications if c.needs_ocr)
        native_count = total_pages - ocr_count
        logger.info(
            f"Classification complete: {native_count} native, {ocr_count} need OCR "
            f"(saved {native_count} image conversions)"
        )

        return classifications

    def get_page_count(self) -> int:
        """Get total number of pages."""
        try:
            doc = fitz.open(self.pdf_path)
            count = doc.page_count
            doc.close()
            return count
        except Exception:
            info = pdfinfo_from_path(
                str(self.pdf_path),
                poppler_path=config.POPPLER_PATH if os.name == "nt" else None,
            )
            return info["Pages"]

    def convert_all_pages_to_images(self, run_id: str = None) -> List[str]:
        """
        Fallback: Convert all pages to images (like old method).
        Only used if forced or for special cases.
        """
        if not run_id:
            run_id = uuid.uuid4().hex[:8]

        self.output_images_dir.mkdir(parents=True, exist_ok=True)

        images = convert_from_path(
            str(self.pdf_path),
            dpi=config.DPI,
            fmt=config.OUTPUT_FORMAT,
            thread_count=4,
            poppler_path=config.POPPLER_PATH if os.name == "nt" else None,
        )

        saved = []
        for i, img in enumerate(images, start=1):
            filename = f"page_{i}_{run_id}.{config.OUTPUT_FORMAT}"
            img_path = self.output_images_dir / filename
            img.save(str(img_path), config.OUTPUT_FORMAT.upper(), optimize=True)
            saved.append(str(img_path))
            logger.info(f"Saved: {img_path}")

        return saved
