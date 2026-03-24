import streamlit as st
from google import genai
from PIL import Image
import os
import sys
import json
import uuid
import re
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from pdf import PDFToImageConverter

# -----------------------------------
# Force UTF-8
# -----------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------
# Load environment variables
# -----------------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# -----------------------------------
# Absolute base directory (wherever app.py lives)
# -----------------------------------
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_IMAGES_DIR = BASE_DIR / "output_images"
JSON_OUTPUT_DIR = BASE_DIR / "output_jsons"
MERGED_OUTPUT_DIR = BASE_DIR / "merged_outputs"


# ==========================================
# HELPERS
# ==========================================


def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


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


def save_json_text(text: str, output_path: Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def sanitize_filename(name: str) -> str:
    """Remove characters that are unsafe in filenames on Windows."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


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
# STREAMLIT UI
# ==========================================

st.set_page_config(page_title="PDF OCR", page_icon="📄", layout="wide")
st.title("📄 PDF OCR — Gemini 2.5 Flash")
st.caption(
    "Upload a PDF. Each page is converted to an image, OCR'd by Gemini, saved as individual JSON files, then merged into one."
)

# --- API Key check ---
if not GOOGLE_API_KEY:
    st.error("❌ GEMINI_API_KEY not found. Add it to your .env file.")
    st.stop()

# --- Upload widget ---
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file is not None:
    st.info(f"File: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

    if st.button("▶ Run OCR Pipeline", type="primary"):

        # Save uploaded PDF to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_pdf_path = tmp.name

        run_id = uuid.uuid4().hex[:8]
        pdf_stem = sanitize_filename(Path(uploaded_file.name).stem)

        # Per-run subdirectories so runs don't collide
        run_images_dir = OUTPUT_IMAGES_DIR / run_id
        run_json_dir = JSON_OUTPUT_DIR / run_id
        MERGED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        pipeline_ok = True

        # ---- STEP 1: PDF → Images ----
        image_paths = []
        with st.status("Step 1 — Converting PDF to images…", expanded=True) as status:
            try:
                converter = PDFToImageConverter(tmp_pdf_path, str(run_images_dir))
                image_paths = converter.convert()
                status.update(
                    label=f"✅ Step 1 — {len(image_paths)} page(s) converted.",
                    state="complete",
                )
            except Exception as e:
                status.update(label=f"❌ Step 1 failed: {e}", state="error")
                pipeline_ok = False

        if not pipeline_ok:
            os.unlink(tmp_pdf_path)
            st.stop()

        # ---- STEP 2: OCR each image ----
        client = genai.Client(api_key=GOOGLE_API_KEY)
        saved_json_files = []
        run_json_dir.mkdir(parents=True, exist_ok=True)

        with st.status("Step 2 — Running OCR on each page…", expanded=True) as status:
            progress = st.progress(0)
            for i, image_path in enumerate(image_paths, start=1):
                image_stem = Path(image_path).stem
                json_path = run_json_dir / f"{image_stem}.json"

                status.write(
                    f"Processing page {i}/{len(image_paths)}: `{Path(image_path).name}`"
                )
                try:
                    ocr_text = ocr_image(client, image_path)
                    save_json_text(ocr_text, json_path)
                    saved_json_files.append(json_path)
                except Exception as e:
                    status.write(f"⚠️ Page {i} failed: {e}")

                progress.progress(i / len(image_paths))

            status.update(
                label=f"✅ Step 2 — OCR complete ({len(saved_json_files)}/{len(image_paths)} pages).",
                state="complete",
            )

        # ---- STEP 3: Merge ----
        merged_output_path = MERGED_OUTPUT_DIR / f"{pdf_stem}_{run_id}.json"
        with st.status("Step 3 — Merging JSON files…", expanded=True) as status:
            try:
                merged_data = merge_json_files(saved_json_files)
                merged_output_path.write_text(
                    json.dumps(merged_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                status.update(label="✅ Step 3 — Merged JSON saved.", state="complete")
            except Exception as e:
                status.update(label=f"❌ Step 3 failed: {e}", state="error")
                pipeline_ok = False

        # Clean up temp PDF
        try:
            os.unlink(tmp_pdf_path)
        except Exception:
            pass

        if not pipeline_ok:
            st.stop()

        # ---- RESULTS ----
        st.success("✅ Pipeline complete!")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Pages processed", len(saved_json_files))
        with col2:
            st.metric("Merged output", Path(merged_output_path).name)

        # Download merged JSON
        with open(merged_output_path, "r", encoding="utf-8") as f:
            merged_bytes = f.read().encode("utf-8")

        st.download_button(
            label="⬇ Download merged JSON",
            data=merged_bytes,
            file_name=Path(merged_output_path).name,
            mime="application/json",
        )

        # Per-page preview
        st.subheader("Per-page Results")
        for i, json_file in enumerate(saved_json_files, start=1):
            with st.expander(f"Page {i} — {Path(json_file).name}"):
                # Show thumbnail
                img_path = image_paths[i - 1]
                st.image(img_path, caption=f"Page {i}", use_container_width=True)

                # Show JSON
                with open(json_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                cleaned = clean_json_text(raw)
                try:
                    parsed = json.loads(cleaned)
                    st.json(parsed)
                except json.JSONDecodeError:
                    st.code(raw, language="text")

                # Download individual JSON
                st.download_button(
                    label=f"⬇ Download Page {i} JSON",
                    data=raw.encode("utf-8"),
                    file_name=Path(json_file).name,
                    mime="application/json",
                    key=f"dl_{i}",
                )
