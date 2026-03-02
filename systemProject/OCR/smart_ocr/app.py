"""
Smart OCR — Streamlit Dashboard
Production-grade PDF OCR with Bangla-first accuracy, cost optimization, and old-format JSON output.
"""

import streamlit as st
import json
import os
import sys
import time
import tempfile
from pathlib import Path

# Add parent to path so we can import smart_ocr
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from smart_ocr.pipeline import SmartOCRPipeline
from smart_ocr import config
from smart_ocr.output_handler import clean_json_text

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Smart OCR — PDF Processing",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# SIDEBAR — Settings
# ==========================================
with st.sidebar:
    st.title("⚙️ Settings")

    st.subheader("Processing Mode")
    processing_mode = st.radio(
        "OCR Strategy",
        [
            "🧠 Smart (Recommended)",
            "🔍 PaddleOCR + Gemini Fallback",
            "🤖 Gemini Only (Old Method)",
        ],
        index=0,
        help=(
            "**Smart**: Tries native text first, PaddleOCR for images, Gemini only for low-confidence blocks.\n\n"
            "**PaddleOCR + Gemini**: Always runs PaddleOCR on images, falls back to Gemini.\n\n"
            "**Gemini Only**: Converts all pages to images and sends to Gemini (like old method)."
        ),
    )

    use_paddle = processing_mode != "🤖 Gemini Only (Old Method)"
    force_gemini = processing_mode == "🤖 Gemini Only (Old Method)"

    st.divider()

    st.subheader("Confidence Thresholds")
    high_conf = st.slider(
        "High confidence", 0.5, 1.0, config.HIGH_CONFIDENCE_THRESHOLD, 0.05
    )
    medium_conf = st.slider(
        "Medium confidence", 0.3, 0.9, config.MEDIUM_CONFIDENCE_THRESHOLD, 0.05
    )

    # Apply to config
    config.HIGH_CONFIDENCE_THRESHOLD = high_conf
    config.MEDIUM_CONFIDENCE_THRESHOLD = medium_conf

    st.divider()

    st.subheader("About")
    st.caption(
        "Smart OCR System v1.0\n\n"
        "• Bangla-first accuracy\n"
        "• Native text extraction first\n"
        "• PaddleOCR for scanned pages\n"
        "• Gemini only for low-confidence blocks\n"
        "• Block-level routing\n"
        "• Old JSON format output"
    )

# ==========================================
# MAIN UI
# ==========================================
st.title("🧠 Smart OCR — PDF Processing")
st.caption(
    "Upload a PDF. The system intelligently decides: native extraction, PaddleOCR, or Gemini — "
    "per-page, per-block. Output JSON is compatible with the old format."
)

# API Key check
if not config.GEMINI_API_KEY:
    st.error("❌ `GEMINI_API_KEY` not found in your `.env` file. Add it and restart.")
    st.stop()

# File upload
uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"])

if uploaded_file is not None:
    file_size_kb = uploaded_file.size / 1024
    st.info(f"**{uploaded_file.name}** — {file_size_kb:.1f} KB")

    if st.button("▶ Run Smart OCR Pipeline", type="primary", use_container_width=True):

        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_pdf_path = tmp.name

        # Progress containers
        status_container = st.empty()
        progress_bar = st.progress(0)
        detail_container = st.empty()

        # Progress callback for the pipeline
        def on_progress(step: str, detail: str, progress: float):
            progress_bar.progress(min(progress, 1.0))
            status_container.markdown(f"**{step}**: {detail}")

        # Build pipeline
        pipeline_ok = True
        result = None

        try:
            with st.status("Running Smart OCR Pipeline...", expanded=True) as status:
                status.write("🔄 Initializing pipeline...")

                pipeline = SmartOCRPipeline(
                    pdf_path=tmp_pdf_path,
                    progress_callback=on_progress,
                    use_paddle=use_paddle,
                    force_gemini_all=force_gemini,
                )

                status.write("📑 Classifying pages...")
                result = pipeline.run()

                status.update(
                    label=f"✅ Pipeline complete — {result.total_pages} pages processed in {result.processing_time_ms:.0f}ms",
                    state="complete",
                )

        except Exception as e:
            st.error(f"❌ Pipeline failed: {e}")
            pipeline_ok = False
        finally:
            try:
                os.unlink(tmp_pdf_path)
            except Exception:
                pass

        if not pipeline_ok or result is None:
            st.stop()

        # Clear progress
        progress_bar.empty()
        status_container.empty()
        detail_container.empty()

        # ==========================================
        # RESULTS
        # ==========================================
        st.success("✅ Pipeline complete!")

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Pages", result.total_pages)
        with col2:
            st.metric("Confidence", f"{result.overall_confidence:.1%}")
        with col3:
            gemini_calls = result.gemini_usage_summary.get("total_api_calls", 0)
            st.metric("Gemini Calls", gemini_calls)
        with col4:
            cache_hits = result.gemini_usage_summary.get("cache_hits", 0)
            st.metric("Cache Hits", cache_hits)

        # Cost savings info
        native_pages = sum(1 for p in result.pages if p.source_type == "native_text")
        if native_pages > 0:
            st.info(
                f"💰 **Cost optimization**: {native_pages}/{result.total_pages} pages used native text extraction "
                f"(no image conversion or API calls needed)"
            )

        # Download merged JSON (old format)
        st.subheader("📥 Download Results")

        old_json = result.to_old_json()
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="⬇ Download Merged JSON (Old Format)",
                data=old_json.encode("utf-8"),
                file_name=f"merged_{pipeline.run_id}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_dl2:
            full_json = result.to_json()
            st.download_button(
                label="⬇ Download Full JSON (With Metadata)",
                data=full_json.encode("utf-8"),
                file_name=f"full_{pipeline.run_id}.json",
                mime="application/json",
                use_container_width=True,
            )

        # ==========================================
        # Per-Page Results
        # ==========================================
        st.subheader("📄 Per-Page Results")

        for page in result.pages:
            source_emoji = {
                "native_text": "📝",
                "ocr": "🔍",
                "hybrid": "🔀",
            }.get(page.source_type, "❓")

            with st.expander(
                f"Page {page.page_id} — {source_emoji} {page.source_type} "
                f"(conf: {page.page_confidence_score:.1%}, "
                f"blocks: {len(page.blocks)}, "
                f"time: {page.processing_time_ms:.0f}ms)"
            ):
                # Show image if available
                if page.image_path and os.path.exists(page.image_path):
                    st.image(
                        page.image_path,
                        caption=f"Page {page.page_id}",
                        use_container_width=True,
                    )

                # Language distribution
                lang_dist = page.page_language_distribution
                if lang_dist:
                    st.caption(
                        f"Languages: Bangla {lang_dist.get('bangla', 0):.0%} | "
                        f"English {lang_dist.get('english', 0):.0%} | "
                        f"Mixed {lang_dist.get('mixed', 0):.0%}"
                    )

                # Per-block details
                for block in page.blocks:
                    route_color = {
                        "accept": "🟢",
                        "local_correction": "🟡",
                        "gemini_fallback": "🔴",
                    }.get(block.routing_decision, "⚪")

                    gemini_tag = " [Gemini]" if block.gemini_used else ""

                    st.markdown(
                        f"**{block.block_id}** {route_color} conf={block.confidence_score:.3f} "
                        f"| {block.detected_language_type} "
                        f"(bn={block.bangla_ratio:.0%} en={block.english_ratio:.0%})"
                        f"{gemini_tag}"
                    )

                    # Show corrected text
                    text = (
                        block.corrected_text if block.corrected_text else block.raw_text
                    )
                    if text.strip():
                        st.text(text[:500] + ("..." if len(text) > 500 else ""))

                st.divider()

                # Show page JSON
                with st.popover("View Page JSON"):
                    st.json(page.to_dict())

        # ==========================================
        # Document Summary
        # ==========================================
        st.subheader("📊 Document Summary")

        with st.expander("Gemini Usage Summary"):
            st.json(result.gemini_usage_summary)

        with st.expander("Language Distribution"):
            st.json(result.language_distribution_summary)

        with st.expander("Full Merged JSON Preview"):
            try:
                parsed = json.loads(old_json)
                st.json(parsed)
            except json.JSONDecodeError:
                st.code(old_json, language="json")
