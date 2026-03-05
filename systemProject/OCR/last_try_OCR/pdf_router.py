"""
PDF Router — Page-level type detection using PyMuPDF.
Determines whether each page is digital-text or scanned,
and renders pages to images only when necessary.
"""

import logging
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF

from . import config

logger = logging.getLogger(__name__)

# Minimum chars to consider a page as having extractable text
_MIN_TEXT_LENGTH = 30


def open_pdf(pdf_path: str | Path) -> fitz.Document:
    """Open a PDF and return the fitz Document."""
    return fitz.open(str(pdf_path))


def detect_page_type(page: fitz.Page) -> str:
    """
    Returns 'digital' if the page contains extractable Unicode text,
    otherwise 'scanned'.
    """
    text = page.get_text("text").strip()
    if len(text) >= _MIN_TEXT_LENGTH:
        return "digital"
    return "scanned"


def extract_digital_text(page: fitz.Page) -> str:
    """Extract raw digital text from a page via PyMuPDF."""
    return page.get_text("text")


def render_page_to_image(page: fitz.Page, dpi: int = None) -> bytes:
    """
    Render a single page to a PNG image at the given DPI.
    Returns raw PNG bytes.
    """
    if dpi is None:
        dpi = config.DPI
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def extract_page_images(page: fitz.Page) -> List[dict]:
    """
    Extract embedded images from a page.
    Returns a list of dicts with 'xref', 'bbox', 'image_bytes', 'ext'.
    """
    images = []
    img_list = page.get_images(full=True)
    doc = page.parent
    for idx, img_info in enumerate(img_list):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            if base_image:
                images.append(
                    {
                        "xref": xref,
                        "image_bytes": base_image["image"],
                        "ext": base_image.get("ext", "png"),
                        "width": base_image.get("width", 0),
                        "height": base_image.get("height", 0),
                    }
                )
        except Exception as e:
            logger.warning("Failed to extract image xref=%d: %s", xref, e)
    return images


def route_pdf(pdf_path: str | Path) -> List[Tuple[int, str]]:
    """
    Analyze every page in the PDF and return a list of
    (page_number, page_type) where page_type is 'digital' or 'scanned'.
    Page numbers are 1-indexed.
    """
    doc = open_pdf(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        ptype = detect_page_type(page)
        results.append((page_num + 1, ptype))
        logger.info("Page %d → %s", page_num + 1, ptype)
    doc.close()
    return results
