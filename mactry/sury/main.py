import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Important for M4

import sys
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF - pip install pymupdf
from surya.common.surya.schema import TaskNames
from surya.detection import DetectionPredictor
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor

LANGS = ["bn"]  # Bengali
DPI = 300       # Higher = better accuracy

# --- Step 1: Convert PDF pages to images ---
def pdf_to_images(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images

def extract_text(predictions) -> str:
    full_text = ""
    for page_num, page_pred in enumerate(predictions, 1):
        page_text = "\n".join([line.text for line in page_pred.text_lines])
        full_text += f"\n{'='*40}\nPage {page_num}\n{'='*40}\n{page_text}\n"
    return full_text


def process_pdf(pdf_path: str, det_predictor, rec_predictor) -> None:
    if not Path(pdf_path).exists():
        print(f"Skipping missing file: {pdf_path}")
        return

    images = pdf_to_images(pdf_path, dpi=DPI)
    print(f"Processing {pdf_path} ({len(images)} page(s))...")

    task_names = [TaskNames.ocr_with_boxes] * len(images)
    predictions = rec_predictor(
        images,
        task_names=task_names,
        det_predictor=det_predictor,
        highres_images=images,
        math_mode=False,
    )

    full_text = extract_text(predictions)
    output_path = Path(pdf_path).stem + "_ocr.txt"
    Path(output_path).write_text(full_text, encoding="utf-8")
    print(f"Done. Saved to: {output_path}")
    print(full_text[:500])


def main() -> None:
    pdf_paths = sys.argv[1:]
    if not pdf_paths:
        print("Usage: python main.py <pdf1> [pdf2 ...]")
        raise SystemExit(1)

    # Load once and reuse for all files.
    print("Loading models (first run downloads ~1GB)...")
    foundation_predictor = FoundationPredictor()
    det_predictor = DetectionPredictor()
    rec_predictor = RecognitionPredictor(foundation_predictor)

    for pdf_path in pdf_paths:
        process_pdf(pdf_path, det_predictor, rec_predictor)


if __name__ == "__main__":
    main()