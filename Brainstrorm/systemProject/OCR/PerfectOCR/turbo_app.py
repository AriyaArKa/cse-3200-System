"""
TurbOCR — Ultra-Fast Streamlit Dashboard
=========================================

Clean, minimal UI:
- Upload multiple PDFs
- Auto-process with optimal settings
- Stream results as they complete
- Export all results

No user configuration needed — optimized settings by default.
"""

import streamlit as st
import os
import sys
import time
import json
import tempfile
from pathlib import Path
from typing import List, Dict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from PerfectOCR.turbo_pipeline import TurboOCREngine, BatchProcessor, DocumentOCRResult
from PerfectOCR import config

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="TurbOCR — Fast PDF OCR",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================
# CUSTOM CSS — Clean Modern Design
# ==========================================
st.markdown(
    """
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Clean header */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    
    /* Upload zone */
    .upload-zone {
        border: 2px dashed #667eea;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
        transition: all 0.3s ease;
    }
    .upload-zone:hover {
        border-color: #764ba2;
        background: linear-gradient(135deg, #e8ebf0 0%, #d4d8db 100%);
    }
    
    /* Result card */
    .result-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    /* Stats badge */
    .stat-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 2px;
    }
    .stat-pages { background: #e0f2fe; color: #0369a1; }
    .stat-time { background: #dcfce7; color: #15803d; }
    .stat-api { background: #fef3c7; color: #b45309; }
    
    /* Progress */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Hide sidebar completely */
    [data-testid="stSidebar"] {display: none;}
    
    /* Fullwidth content */
    .block-container {
        max-width: 1200px;
        padding-top: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# HEADER
# ==========================================
st.markdown('<h1 class="main-header">⚡ TurbOCR</h1>', unsafe_allow_html=True)
st.caption(
    "Ultra-fast PDF OCR with Gemini AI • Supports Bangla & English • Multiple file upload"
)

# ==========================================
# FILE UPLOAD
# ==========================================
uploaded_files = st.file_uploader(
    "Drop PDFs here",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="Upload one or more PDF files for OCR processing",
)

if not uploaded_files:
    st.markdown(
        """
    <div class="upload-zone">
        <h3>📄 Drop PDF files here</h3>
        <p style="color: #666;">Supports multiple files • Bangla & English • Tables & Handwriting</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Feature highlights
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⚡ Speed", "< 2s/page", help="Optimized native PDF processing")
    with col2:
        st.metric("🎯 Accuracy", "Bengali digits", help="Enhanced ০-৯ recognition")
    with col3:
        st.metric("💰 Cost", "Minimal API", help="Native PDF = 258 tokens/page")

    st.stop()

# ==========================================
# PROCESSING
# ==========================================

# Save uploaded files to temp location
temp_dir = tempfile.mkdtemp()
pdf_paths = []

for uploaded_file in uploaded_files:
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())
    pdf_paths.append(temp_path)

# Processing UI
st.divider()

# Stats placeholder
stats_container = st.container()

# Progress
progress_bar = st.progress(0)
status_text = st.empty()

# Results container
results_container = st.container()

# Initialize processor
processor = BatchProcessor()
all_results: Dict[str, DocumentOCRResult] = {}

total_files = len(pdf_paths)
completed_files = 0
total_pages_processed = 0
total_api_calls = 0
start_time = time.time()

# Process each file
for i, pdf_path in enumerate(pdf_paths):
    filename = Path(pdf_path).name

    status_text.markdown(f"**Processing:** {filename} ({i+1}/{total_files})")

    # Per-file progress
    def file_progress(current, total, status):
        overall_progress = (i + current / max(total, 1)) / total_files
        progress_bar.progress(min(overall_progress, 1.0))
        status_text.markdown(f"**{filename}:** {status} ({current}/{total} pages)")

    try:
        engine = TurboOCREngine()
        result = engine.extract_all_pages(pdf_path, file_progress)
        all_results[filename] = result

        total_pages_processed += result.total_pages
        total_api_calls += result.api_calls

    except Exception as e:
        st.error(f"❌ Failed: {filename} — {str(e)}")
        all_results[filename] = DocumentOCRResult(
            filename=filename,
            total_pages=0,
            pages=[],
            processing_time_ms=0,
            api_calls=0,
        )

    completed_files += 1

# Complete
progress_bar.progress(1.0)
total_time = (time.time() - start_time) * 1000
status_text.empty()

# ==========================================
# STATISTICS
# ==========================================
with stats_container:
    st.success(f"✅ Processed {completed_files} file(s) in {total_time/1000:.1f}s")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Files", completed_files)
    with col2:
        st.metric("📑 Pages", total_pages_processed)
    with col3:
        avg_time = total_time / max(total_pages_processed, 1)
        st.metric("⚡ Avg/Page", f"{avg_time:.0f}ms")
    with col4:
        st.metric("🔵 API Calls", total_api_calls)

st.divider()

# ==========================================
# RESULTS
# ==========================================
with results_container:

    # Download all button
    if all_results:
        all_data = {
            "summary": {
                "total_files": completed_files,
                "total_pages": total_pages_processed,
                "processing_time_ms": total_time,
                "api_calls": total_api_calls,
            },
            "documents": {
                name: result.to_dict() for name, result in all_results.items()
            },
        }

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇ Download All (JSON)",
                data=json.dumps(all_data, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="turbo_ocr_results.json",
                mime="application/json",
                use_container_width=True,
            )
        with col2:
            all_text = (
                "\n\n"
                + "=" * 60
                + "\n\n".join(
                    f"FILE: {name}\n{'='*60}\n{result.get_full_text()}"
                    for name, result in all_results.items()
                )
            )
            st.download_button(
                "⬇ Download All (Text)",
                data=all_text.encode("utf-8"),
                file_name="turbo_ocr_results.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.divider()

    # Per-file results
    for filename, result in all_results.items():
        with st.expander(
            f"📄 {filename} — {result.total_pages} pages • {result.processing_time_ms:.0f}ms",
            expanded=len(all_results) == 1,
        ):

            # File stats
            st.markdown(
                f"""
            <span class="stat-badge stat-pages">📑 {result.total_pages} pages</span>
            <span class="stat-badge stat-time">⏱️ {result.processing_time_ms:.0f}ms</span>
            <span class="stat-badge stat-api">🔵 {result.api_calls} API calls</span>
            """,
                unsafe_allow_html=True,
            )

            # Full text
            st.markdown("### 📝 Extracted Text")
            full_text = result.get_full_text()
            if full_text:
                st.text_area(
                    "Full text",
                    value=full_text,
                    height=400,
                    key=f"text_{id(result)}_{filename}",
                    label_visibility="collapsed",
                )
            else:
                st.caption("No text extracted")

            # Per-page details (collapsed by default)
            if result.pages:
                with st.expander("📋 Page Details"):
                    for page in sorted(result.pages, key=lambda x: x.page_number):
                        st.markdown(
                            f"**Page {page.page_number}** — {len(page.blocks)} blocks • {page.source}"
                        )

                        # Show tables if any
                        for table in page.tables:
                            if "data" in table and table["data"]:
                                try:
                                    import pandas as pd

                                    df = pd.DataFrame(
                                        table["data"][1:],
                                        columns=(
                                            table["data"][0]
                                            if len(table["data"]) > 1
                                            else None
                                        ),
                                    )
                                    st.dataframe(df, use_container_width=True)
                                except Exception:
                                    st.json(table)

                        # Notes/errors
                        if page.notes:
                            for note in page.notes:
                                st.caption(f"⚠️ {note}")

                        st.markdown("---")

            # JSON view
            with st.expander("🔍 JSON"):
                st.json(result.to_dict())

# Cleanup temp files
try:
    import shutil

    shutil.rmtree(temp_dir)
except Exception:
    pass

# ==========================================
# FOOTER
# ==========================================
st.divider()
st.caption(
    "TurbOCR v3.0 • Native PDF → Gemini • Parallel Processing • Minimal API Calls"
)
