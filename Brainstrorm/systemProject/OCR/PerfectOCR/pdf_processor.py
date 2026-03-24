"""
PDF Processor Module for PerfectOCR.
Converts PDF pages to high-quality images for OCR.
"""

import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF

from . import config

logger = logging.getLogger(__name__)


@dataclass
class PageImage:
    """A single page converted to image."""

    page_number: int
    image_bytes: bytes
    image_b64: str
    image_path: str = ""


class PDFProcessor:
    """
    Converts PDF pages to high-quality PNG images.
    Uses PyMuPDF (fitz) for fast, dependency-free conversion.
    """

    def __init__(self, pdf_path: str, output_dir: str = None):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir or config.OUTPUT_IMAGES_DIR)
        self._validate_pdf()

    def _validate_pdf(self):
        """Validate the PDF file."""
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

    def get_page_count(self) -> int:
        """Get total number of pages."""
        doc = fitz.open(str(self.pdf_path))
        count = doc.page_count
        doc.close()
        return count

    def convert_to_images(
        self,
        dpi: int = None,
        run_id: str = "",
        progress_callback=None,
    ) -> List[PageImage]:
        """
        Convert all PDF pages to PNG images.

        Args:
            dpi: Resolution (default from config)
            run_id: Unique run identifier for file naming
            progress_callback: fn(page_num, total, message)

        Returns:
            List of PageImage with bytes, base64, and saved path
        """
        dpi = dpi or config.DPI
        doc = fitz.open(str(self.pdf_path))
        total_pages = doc.page_count
        images: List[PageImage] = []

        # Ensure output directory exists
        save_dir = self.output_dir / run_id if run_id else self.output_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        for page_num in range(total_pages):
            if progress_callback:
                progress_callback(
                    page_num + 1,
                    total_pages,
                    f"Converting page {page_num + 1}/{total_pages}",
                )

            page = doc.load_page(page_num)
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.b64encode(img_bytes).decode()

            # Save image file
            filename = f"page_{page_num + 1}.png"
            img_path = save_dir / filename
            with open(str(img_path), "wb") as f:
                f.write(img_bytes)

            images.append(
                PageImage(
                    page_number=page_num + 1,
                    image_bytes=img_bytes,
                    image_b64=img_b64,
                    image_path=str(img_path),
                )
            )

            logger.info(f"Converted page {page_num + 1}/{total_pages}")

        doc.close()
        logger.info(f"Converted {len(images)} pages to images at {dpi} DPI")
        return images

    def convert_single_page(self, page_num: int, dpi: int = None) -> PageImage:
        """
        Convert a single page to image (0-indexed).

        Args:
            page_num: 0-indexed page number
            dpi: Resolution

        Returns:
            PageImage
        """
        dpi = dpi or config.DPI
        doc = fitz.open(str(self.pdf_path))
        page = doc.load_page(page_num)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode()
        doc.close()

        return PageImage(
            page_number=page_num + 1,
            image_bytes=img_bytes,
            image_b64=img_b64,
        )
