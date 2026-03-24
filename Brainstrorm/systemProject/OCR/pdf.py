import os
import uuid
import logging
from pathlib import Path
from typing import List
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image


# ==========================================
# CONFIGURATION
# ==========================================

POPPLER_PATH = r"D:\3-2\system\Release-25.12.0-0\poppler-25.12.0\Library\bin"  # Change if needed (Windows only)
DPI = 300
OUTPUT_FORMAT = "png"  # png recommended for OCR
MAX_PDF_SIZE_MB = 25   # safety limit


# ==========================================
# LOGGING SETUP
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ==========================================
# PDF TO IMAGE CONVERTER CLASS
# ==========================================

class PDFToImageConverter:

    def __init__(self, pdf_path: str, output_dir: str = "output_images"):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)

        self._validate_pdf()
        self._create_output_dir()

    def _validate_pdf(self):
        """Validate PDF existence and size."""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError("File must be a PDF")

        size_mb = self.pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_PDF_SIZE_MB:
            raise ValueError(f"PDF exceeds {MAX_PDF_SIZE_MB}MB limit")

        logging.info(f"PDF validated. Size: {size_mb:.2f} MB")

    def _create_output_dir(self):
        """Create output directory if not exists."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def convert(self) -> List[str]:
        """Convert PDF to high-resolution images."""
        try:
            logging.info("Reading PDF metadata...")
            info = pdfinfo_from_path(
                self.pdf_path,
                poppler_path=POPPLER_PATH if os.name == "nt" else None
            )
            total_pages = info["Pages"]
            logging.info(f"Total Pages: {total_pages}")

            logging.info("Converting PDF pages to images...")
            images = convert_from_path(
                self.pdf_path,
                dpi=DPI,
                fmt=OUTPUT_FORMAT,
                thread_count=4,
                poppler_path=POPPLER_PATH if os.name == "nt" else None
            )

            saved_files = []

            for i, image in enumerate(images, start=1):
                filename = f"{self.pdf_path.stem}_page_{i}_{uuid.uuid4().hex[:8]}.{OUTPUT_FORMAT}"
                output_path = self.output_dir / filename

                image.save(output_path, OUTPUT_FORMAT.upper(), optimize=True)
                saved_files.append(str(output_path))

                logging.info(f"Saved: {output_path}")

            logging.info("PDF conversion completed successfully.")
            return saved_files

        except Exception as e:
            logging.error(f"Error converting PDF: {str(e)}")
            raise


# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    pdf_file = "invoice.pdf"  # Change to your PDF filename

    try:
        converter = PDFToImageConverter(pdf_file)
        image_paths = converter.convert()

        print("\nConverted Images:")
        for path in image_paths:
            print(path)

    except Exception as err:
        print(f"\nConversion failed: {err}")