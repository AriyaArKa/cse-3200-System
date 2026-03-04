"""
PerfectOCR — Streamlit Dashboard
Dual-model OCR (GPT-4o + Gemini) for mixed Bangla/English documents.
"""

import streamlit as st
import json
import os
import sys
import time
import tempfile
from pathlib import Path

# Add parent to path so we can import PerfectOCR
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from PerfectOCR.pipeline import PerfectOCRPipeline
from PerfectOCR import config

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="PerfectOCR — Dual Model OCR",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# CUSTOM CSS
# ==========================================
st.markdown(
    """
<style>
    .block-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
    .source-gpt4o { color: #6f42c1; }
    .source-gemini { color: #0d6efd; }
    .stMetric > div { text-align: center; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# SIDEBAR — Settings
# ==========================================
with st.sidebar:
    st.title("⚙️ Settings")

    # Auto-strategy info
    st.subheader("OCR Strategy")

    # Check if fast OCR is available
    try:
        from PerfectOCR.fast_ocr import TESSERACT_AVAILABLE

        fast_ocr_available = TESSERACT_AVAILABLE
    except:
        fast_ocr_available = False

    if fast_ocr_available:
        st.success(
            "⚡ **Fast OCR Enabled**\n\n"
            "Simple English text → Tesseract (no API calls)\n"
            "Complex/Bangla/handwriting → Gemini + GPT-4o fallback"
        )
    else:
        st.info(
            "🔵 **Gemini Primary** (auto-selected)\n\n"
            "Uses Gemini 2.5 Flash as the primary OCR engine. "
            "GPT-4o is used as fallback only when Gemini fails.\n\n"
            "✅ Optimal for long PDFs\n"
            "✅ Fewer API calls\n"
            "✅ Best Bangla accuracy"
        )
        st.caption(
            "💡 Install `pytesseract` and Tesseract OCR for even faster processing of simple English documents"
        )

    selected_strategy = "gemini_primary"

    st.divider()

    # DPI
    st.subheader("Image Quality")
    dpi = st.slider(
        "DPI",
        100,
        400,
        config.DPI,
        50,
        help="Higher DPI = better quality but slower. 250+ recommended for handwriting.",
    )

    st.divider()

    # Correction toggle
    st.subheader("Post-Processing")
    enable_correction = st.checkbox(
        "Enable Bangla Correction",
        value=config.ENABLE_BANGLA_CORRECTION,
        help="Run an LLM correction pass to fix Bangla OCR errors (mattra, hasanta, conjuncts)",
    )

    correction_model = st.selectbox(
        "Correction Model",
        ["gemini-2.5-flash", "gpt-4o"],
        index=0,
        help="Which model to use for the Bangla correction pass. Gemini recommended (fewer GPT-4o API calls).",
    )

    st.divider()

    # API Key status
    st.subheader("API Status")
    gemini_ok = bool(config.GEMINI_API_KEY)
    openai_ok = bool(config.OPENAI_API_KEY)
    st.markdown(f"{'✅' if gemini_ok else '❌'} Gemini API Key")
    st.markdown(f"{'✅' if openai_ok else '❌'} OpenAI API Key")

    if not gemini_ok and selected_strategy in ("dual", "gemini_primary", "gemini_only"):
        st.warning("⚠️ Gemini API key missing! Add `GEMINI_API_KEY` to `.env`")

    if not openai_ok and selected_strategy in ("dual", "gpt4o_primary", "gpt4o_only"):
        st.warning("⚠️ OpenAI API key missing! Add `OPENAI_API_KEY` to `.env`")

    st.divider()

    st.subheader("About")
    st.caption(
        "PerfectOCR v2.0\n\n"
        "• Gemini Primary + GPT-4o Fallback\n"
        "• Bengali numeral accuracy (৫ vs ৩)\n"
        "• Handwritten text & signatures\n"
        "• Image/logo descriptions\n"
        "• Bangla-first accuracy\n"
        "• Structured JSON output\n"
        "• Tables, forms, handwriting\n"
        "• Post-correction for Bangla"
    )

# ==========================================
# MAIN UI
# ==========================================
st.title("🔬 PerfectOCR — Dual Model OCR")
st.caption(
    "Upload a PDF containing mixed Bangla/English content. "
    "The system uses Gemini 2.5 Flash as primary OCR with GPT-4o fallback, "
    "with intelligent Bangla-specific correction and image descriptions."
)

st.info(
    "🔵 **Auto Strategy: Gemini Primary** — Gemini processes each page. GPT-4o is used only if Gemini fails. Optimized for accuracy and cost."
)

# ── File Upload ─────────────────────────────────────────
uploaded_file = st.file_uploader("📄 Upload PDF", type=["pdf"])

if uploaded_file is not None:
    file_size_kb = uploaded_file.size / 1024
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("File", uploaded_file.name)
    with col_info2:
        st.metric("Size", f"{file_size_kb:.1f} KB")
    with col_info3:
        st.metric("Strategy", selected_strategy.replace("_", " ").title())

    if st.button("▶ Run PerfectOCR Pipeline", type="primary", use_container_width=True):

        # ── Save uploaded file to temp ──────────────
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_pdf_path = tmp.name

        # ── Progress UI ─────────────────────────────
        status_container = st.empty()
        progress_bar = st.progress(0)

        def on_progress(step: str, detail: str, progress: float):
            progress_bar.progress(min(progress, 1.0))
            status_container.markdown(f"**{step}**: {detail}")

        # ── Apply correction model setting ──────────
        config.CORRECTION_MODEL = correction_model

        # ── Run Pipeline ────────────────────────────
        pipeline_ok = True
        result = None
        pipeline = None

        try:
            with st.status("Running PerfectOCR Pipeline...", expanded=True) as status:
                status.write("🔄 Initializing pipeline...")

                pipeline = PerfectOCRPipeline(
                    pdf_path=tmp_pdf_path,
                    strategy=selected_strategy,
                    enable_correction=enable_correction,
                    dpi=dpi,
                    progress_callback=on_progress,
                )

                status.write("📑 Converting pages to images...")
                result = pipeline.run()

                status.update(
                    label=(
                        f"✅ Pipeline complete — {result.document.total_pages} pages "
                        f"in {result.processing_time_ms:.0f}ms"
                    ),
                    state="complete",
                )

        except Exception as e:
            st.error(f"❌ Pipeline failed: {e}")
            import traceback

            st.code(traceback.format_exc())
            pipeline_ok = False
        finally:
            try:
                os.unlink(tmp_pdf_path)
            except Exception:
                pass

        if not pipeline_ok or result is None:
            st.stop()

        # ── Clear progress ──────────────────────────
        progress_bar.empty()
        status_container.empty()

        # ==========================================
        # RESULTS
        # ==========================================
        st.success(
            f"✅ Pipeline complete! Processed {result.document.total_pages} pages."
        )

        # ── Metrics row ─────────────────────────────
        tracker = pipeline.tracker if pipeline else None
        tesseract_pages = tracker.tesseract_only_pages if tracker else 0

        if tesseract_pages > 0:
            # Show 6 columns if Tesseract was used
            mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
            with mc1:
                st.metric("📄 Pages", result.document.total_pages)
            with mc2:
                st.metric(
                    "⚡ Fast OCR",
                    tesseract_pages,
                    help="Pages processed by Tesseract only (no AI calls)",
                )
            with mc3:
                gemini_calls = tracker.gemini_calls if tracker else 0
                st.metric("🔵 Gemini", gemini_calls)
            with mc4:
                gpt_calls = tracker.gpt4o_calls if tracker else 0
                st.metric("🟣 GPT-4o", gpt_calls)
            with mc5:
                correction_calls = tracker.correction_calls if tracker else 0
                st.metric("✏️ Corrections", correction_calls)
            with mc6:
                st.metric("⏱️ Time", f"{result.processing_time_ms:.0f}ms")
        else:
            # Original 5 columns
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            with mc1:
                st.metric("📄 Pages", result.document.total_pages)
            with mc2:
                gemini_calls = tracker.gemini_calls if tracker else 0
                st.metric("🔵 Gemini Calls", gemini_calls)
            with mc3:
                gpt_calls = tracker.gpt4o_calls if tracker else 0
                st.metric("🟣 GPT-4o Calls", gpt_calls)
            with mc4:
                correction_calls = tracker.correction_calls if tracker else 0
                st.metric("✏️ Corrections", correction_calls)
            with mc5:
                st.metric("⏱️ Time", f"{result.processing_time_ms:.0f}ms")

        # ── Document features ───────────────────────
        doc = result.document
        feature_cols = st.columns(4)
        with feature_cols[0]:
            st.write(
                f"{'📝' if doc.has_handwriting else '—'} Handwriting: {'Yes' if doc.has_handwriting else 'No'}"
            )
        with feature_cols[1]:
            st.write(
                f"{'📊' if doc.has_tables else '—'} Tables: {'Yes' if doc.has_tables else 'No'}"
            )
        with feature_cols[2]:
            st.write(
                f"{'📋' if doc.has_forms else '—'} Forms: {'Yes' if doc.has_forms else 'No'}"
            )
        with feature_cols[3]:
            st.write(
                f"{'🖼️' if doc.has_images else '—'} Images: {'Yes' if doc.has_images else 'No'}"
            )

        st.divider()

        # ── Download buttons ────────────────────────
        st.subheader("📥 Download Results")

        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            full_json = result.to_json()
            st.download_button(
                label="⬇ Download Full JSON",
                data=full_json.encode("utf-8"),
                file_name=f"perfect_ocr_{pipeline.run_id if pipeline else 'result'}.json",
                mime="application/json",
                use_container_width=True,
            )
        with dl_col2:
            # Full text only
            all_text = "\n\n--- Page Break ---\n\n".join(
                p.full_text_reading_order
                for p in result.pages
                if p.full_text_reading_order
            )
            st.download_button(
                label="⬇ Download Plain Text",
                data=all_text.encode("utf-8"),
                file_name=f"perfect_ocr_{pipeline.run_id if pipeline else 'result'}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.divider()

        # ==========================================
        # PER-PAGE RESULTS
        # ==========================================
        st.subheader("📄 Per-Page Results")

        for page in result.pages:
            # Count block sources
            gemini_blocks = sum(1 for b in page.content_blocks if b._source == "gemini")
            gpt_blocks = sum(1 for b in page.content_blocks if b._source == "gpt4o")

            with st.expander(
                f"Page {page.page_number} — "
                f"{len(page.content_blocks)} blocks "
                f"(🟣 GPT: {gpt_blocks} | 🔵 Gemini: {gemini_blocks}) "
                f"| ⏱️ {page.processing_time_ms:.0f}ms"
            ):
                # ── Page image ──────────────────────
                img_col, text_col = st.columns([1, 1])

                with img_col:
                    if page.image_path and os.path.exists(page.image_path):
                        st.image(
                            page.image_path,
                            caption=f"Page {page.page_number}",
                            use_container_width=True,
                        )

                with text_col:
                    st.markdown("**Full Text (Reading Order):**")
                    if page.full_text_reading_order:
                        # Use combined unique key with index to prevent duplicates
                        page_idx = result.pages.index(page)
                        st.text_area(
                            "Full text",
                            value=page.full_text_reading_order,
                            height=300,
                            key=f"fulltext_{id(result)}_{page_idx}_{page.page_number}",
                            label_visibility="collapsed",
                        )
                    else:
                        st.caption("No text extracted")

                # ── Content blocks ──────────────────
                st.markdown("---")
                st.markdown("**Content Blocks:**")

                for block in page.content_blocks:
                    source_emoji = (
                        "🟣"
                        if block._source == "gpt4o"
                        else "🔵" if block._source == "gemini" else "⚪"
                    )
                    conf_class = {
                        "high": "🟢",
                        "medium": "🟡",
                        "low": "🔴",
                    }.get(block.confidence, "⚪")

                    header = (
                        f"{source_emoji} **Block {block.block_id}** "
                        f"| Type: `{block.type}` "
                        f"| Position: `{block.position}` "
                        f"| Lang: `{block.language}` "
                        f"| {conf_class} {block.confidence} "
                        f"{'| ✍️ Handwritten' if block.is_handwritten else ''}"
                    )
                    st.markdown(header)

                    if block.text:
                        st.text(
                            block.text[:500] + ("..." if len(block.text) > 500 else "")
                        )

                    # Show table data if present
                    if block.table:
                        st.markdown("**Table Data:**")
                        table_data = block.table.get("data", [])
                        if table_data:
                            try:
                                import pandas as pd

                                if len(table_data) > 1:
                                    df = pd.DataFrame(
                                        table_data[1:], columns=table_data[0]
                                    )
                                else:
                                    df = pd.DataFrame(table_data)
                                st.dataframe(df, use_container_width=True)
                            except Exception:
                                st.json(table_data)

                    # Show form fields if present
                    if block.fields:
                        st.markdown("**Form Fields:**")
                        for field in block.fields:
                            filled = "✅" if field.get("is_filled") else "⬜"
                            st.write(
                                f"  {filled} **{field.get('label', '?')}**: "
                                f"{field.get('value', '') or '(empty)'}"
                            )

                    st.markdown("---")

                # ── Tables section ──────────────────
                if page.tables:
                    st.markdown("**Detected Tables:**")
                    for tbl in page.tables:
                        tbl_data = tbl.get("data", [])
                        if tbl_data:
                            try:
                                import pandas as pd

                                if len(tbl_data) > 1 and tbl.get(
                                    "has_header_row", False
                                ):
                                    df = pd.DataFrame(tbl_data[1:], columns=tbl_data[0])
                                else:
                                    df = pd.DataFrame(tbl_data)
                                st.dataframe(df, use_container_width=True)
                            except Exception:
                                st.json(tbl_data)

                # ── Forms section ───────────────────
                if page.forms:
                    st.markdown("**Detected Forms:**")
                    for form in page.forms:
                        for field in form.get("fields", []):
                            filled = "✅" if field.get("is_filled") else "⬜"
                            st.write(
                                f"  {filled} **{field.get('label', '?')}**: "
                                f"{field.get('value', '') or '(empty)'}"
                            )

                # ── Extraction notes ────────────────
                if page.extraction_notes:
                    st.markdown("**Notes:**")
                    for note in page.extraction_notes:
                        st.caption(f"⚠️ {note}")

                # ── View page JSON ──────────────────
                with st.popover("📋 View Page JSON"):
                    st.json(page.to_dict())

        # ==========================================
        # API USAGE SUMMARY
        # ==========================================
        st.divider()
        st.subheader("📊 Pipeline Summary")

        sum_col1, sum_col2 = st.columns(2)

        with sum_col1:
            st.markdown("**API Usage:**")
            if tracker:
                st.json(tracker.to_dict())

        with sum_col2:
            st.markdown("**Document Info:**")
            st.json(result.document.to_dict())

        # ── Full JSON Preview ───────────────────────
        with st.expander("🔍 Full JSON Preview"):
            try:
                parsed = json.loads(full_json)
                st.json(parsed)
            except json.JSONDecodeError:
                st.code(full_json, language="json")
