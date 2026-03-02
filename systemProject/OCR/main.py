from google import genai
from PIL import Image
import os
import sys
import json
import uuid
import re
from pathlib import Path
from dotenv import load_dotenv
from pdf import PDFToImageConverter

# -----------------------------------
# Force UTF-8 output (Fix Bangla issue in Windows)
# -----------------------------------
sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------
# Load environment variables
# -----------------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

# -----------------------------------
# Configuration
# -----------------------------------
#PDF_FILE = "invoiceDemo.pdf"  # Input PDF
PDF_FILE = "বিজ্ঞপ্তি_মহান শহীদ দিবস ও আন্তর্জাতিক মাতৃভাষা দিবস।.pdf"  # Input PDF
OUTPUT_IMAGES_DIR = "output_images"
JSON_OUTPUT_DIR = "output_jsons"  # Individual per-page JSONs
MERGED_OUTPUT_DIR = "merged_outputs"  # Final merged JSONs


# -----------------------------------
# Helper: OCR a single image
# -----------------------------------
def ocr_image(client, image_path: str) -> str:
    image = Image.open(image_path)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            """Extract ALL text exactly as written.
Extract all visible content from this image in STRICT structured JSON format only.
Preserve original Bangla characters exactly.
Do NOT translate.
Return STRICT valid JSON only.
Do NOT include markdown formatting.
Do NOT include explanations.
Ensure UTF-8 correctness.""",
            image,
        ],
    )
    return response.text


# -----------------------------------
# Helper: Strip markdown code fences if present
# -----------------------------------
def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# -----------------------------------
# Helper: Save text to a JSON file (no overwrite)
# -----------------------------------
def save_json_text(text: str, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved: {output_path}")


# -----------------------------------
# Helper: Merge individual JSON files
# -----------------------------------
def merge_json_files(json_files: list) -> dict:
    merged = {"pages": []}
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = clean_json_text(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = {"raw_text": cleaned}
        merged["pages"].append(
            {
                "source_file": os.path.basename(json_file),
                "data": data,
            }
        )
    return merged


# ==========================================
# STEP 1: Convert PDF → Images
# ==========================================
print(f"\n{'='*50}")
print(f"STEP 1: Converting PDF to images...")
print(f"{'='*50}")

converter = PDFToImageConverter(PDF_FILE, OUTPUT_IMAGES_DIR)
image_paths = converter.convert()

print(f"\nConverted {len(image_paths)} page(s).")

# ==========================================
# STEP 2: OCR each image → individual JSON
# ==========================================
print(f"\n{'='*50}")
print(f"STEP 2: Running OCR on each page...")
print(f"{'='*50}")

client = genai.Client(api_key=GOOGLE_API_KEY)
os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
saved_json_files = []

for i, image_path in enumerate(image_paths, start=1):
    image_stem = Path(image_path).stem
    json_path = os.path.join(JSON_OUTPUT_DIR, f"{image_stem}.json")

    print(f"\n[Page {i}] Processing: {image_path}")
    ocr_text = ocr_image(client, image_path)
    save_json_text(ocr_text, json_path)
    saved_json_files.append(json_path)

# ==========================================
# STEP 3: Merge all individual JSONs
# ==========================================
print(f"\n{'='*50}")
print(f"STEP 3: Merging all page JSONs...")
print(f"{'='*50}")

os.makedirs(MERGED_OUTPUT_DIR, exist_ok=True)
run_id = uuid.uuid4().hex[:8]
merged_output_path = os.path.join(MERGED_OUTPUT_DIR, f"merged_{run_id}.json")

merged_data = merge_json_files(saved_json_files)

with open(merged_output_path, "w", encoding="utf-8") as f:
    json.dump(merged_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Done!")
print(f"   Individual JSONs : {JSON_OUTPUT_DIR}/")
print(f"   Merged output    : {merged_output_path}")
