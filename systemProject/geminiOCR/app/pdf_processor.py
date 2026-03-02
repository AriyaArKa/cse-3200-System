"""
PDF → image conversion using pdf2image (Poppler backend).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence

from pdf2image import convert_from_path  # type: ignore
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError  # type: ignore

from app.utils import DPI, create_temp_dir, cleanup_temp_dir, logger


class PDFProcessingError(Exception):
    """Raised when PDF conversion fails."""


async def pdf_to_images(
    pdf_path: Path,
    dpi: int = DPI,
) -> tuple[list[Path], Path]:
    """
    Convert every page of *pdf_path* to a PNG image at the given DPI.

    Returns
    -------
    images : list[Path]
        Ordered list of image file paths (page‑1.png, page‑2.png …).
    job_dir : Path
        Temporary directory holding the images (caller must clean up).
    """
    job_dir = create_temp_dir()

    try:
        # pdf2image is CPU‑bound; run in a thread so we don't block the event loop.
        images_pil = await asyncio.to_thread(
            convert_from_path,
            str(pdf_path),
            dpi=dpi,
            fmt="png",
            thread_count=2,
            output_folder=str(job_dir),
            paths_only=False,
        )
    except (PDFPageCountError, PDFSyntaxError) as exc:
        cleanup_temp_dir(job_dir)
        raise PDFProcessingError(f"Corrupted or invalid PDF: {exc}") from exc
    except Exception as exc:
        cleanup_temp_dir(job_dir)
        raise PDFProcessingError(f"PDF conversion failed: {exc}") from exc

    if not images_pil:
        cleanup_temp_dir(job_dir)
        raise PDFProcessingError("PDF produced zero pages.")

    # Save PIL images as numbered PNGs
    image_paths: list[Path] = []
    for idx, img in enumerate(images_pil, start=1):
        out_path = job_dir / f"page-{idx}.png"
        img.save(str(out_path), "PNG")
        image_paths.append(out_path)
        logger.info("Saved page %d → %s", idx, out_path.name)

    return image_paths, job_dir


def validate_pdf_bytes(data: bytes) -> None:
    """Quick sanity check on raw PDF bytes."""
    if not data[:5] == b"%PDF-":
        raise PDFProcessingError("Uploaded file does not look like a valid PDF.")
