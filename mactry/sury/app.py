import os
import streamlit as st
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import tempfile
from surya.common.surya.schema import TaskNames
from surya.detection import DetectionPredictor
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor

# Set environment variables
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Page config
st.set_page_config(page_title="PDF OCR", layout="wide")
st.title("📄 PDF to Text OCR")
st.markdown("Upload PDF files to extract text using Surya OCR")

# Initialize session state for models (load once)
@st.cache_resource
def load_models():
    """Load OCR models once and cache them."""
    with st.spinner("Loading OCR models (this may take a moment on first run)..."):
        foundation_predictor = FoundationPredictor()
        det_predictor = DetectionPredictor()
        rec_predictor = RecognitionPredictor(foundation_predictor)
    return foundation_predictor, det_predictor, rec_predictor


def pdf_to_images(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    """Convert PDF pages to images."""
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
    """Extract and format text from predictions."""
    full_text = ""
    for page_num, page_pred in enumerate(predictions, 1):
        page_text = "\n".join([line.text for line in page_pred.text_lines])
        full_text += f"\n{'='*50}\nPage {page_num}\n{'='*50}\n{page_text}\n"
    return full_text


def process_pdf(pdf_path: str, det_predictor, rec_predictor) -> str:
    """Process single PDF and return OCR text."""
    images = pdf_to_images(pdf_path, dpi=300)
    task_names = [TaskNames.ocr_with_boxes] * len(images)
    
    predictions = rec_predictor(
        images,
        task_names=task_names,
        det_predictor=det_predictor,
        highres_images=images,
        math_mode=False,
    )
    
    return extract_text(predictions)


# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    dpi_quality = st.slider("PDF Resolution (DPI)", 150, 500, 300, step=50)
    st.info("Higher DPI = Better quality but slower processing")

# Load models
foundation_predictor, det_predictor, rec_predictor = load_models()

# File uploader
uploaded_files = st.file_uploader(
    "Upload PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="You can upload multiple PDF files at once"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
    
    # Process each file
    for uploaded_file in uploaded_files:
        st.subheader(f"📝 {uploaded_file.name}")
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            tmp_path = tmp_file.name
        
        try:
            # Process PDF
            with st.spinner(f"Processing {uploaded_file.name}..."):
                ocr_text = process_pdf(tmp_path, det_predictor, rec_predictor)
            
            # Display results
            st.success(f"✅ OCR completed for {uploaded_file.name}")
            
            # Create columns for better layout
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.text_area(
                    "Extracted Text",
                    value=ocr_text,
                    height=300,
                    disabled=False,
                    key=f"ocr_{uploaded_file.name}"
                )
            
            with col2:
                # Download button
                st.download_button(
                    label="📥 Download TXT",
                    data=ocr_text,
                    file_name=Path(uploaded_file.name).stem + "_ocr.txt",
                    mime="text/plain",
                    key=f"download_{uploaded_file.name}"
                )
            
            st.divider()
        
        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

else:
    st.info("👆 Upload PDF files to get started. You can upload multiple files at once.")
    st.markdown("""
    ### Features:
    - ✨ Extract text from PDF pages
    - 📤 Download results as TXT files
    - 🚀 Process multiple PDFs together
    - ⚙️ Adjustable image quality settings
    """)
