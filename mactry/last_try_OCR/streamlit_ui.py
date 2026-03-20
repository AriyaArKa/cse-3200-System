"""
Streamlit UI — Upload multiple PDFs and view OCR results.
"""

import json
import os
import re
import shutil
import tempfile

import streamlit as st

# Fix import path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from last_try_OCR.pipeline import process_pdf
from last_try_OCR.api_fallback import get_api_stats, reset_api_stats, get_service_status


# ── Corruption helpers ────────────────────────────────────────────────────────
_CID_RE = re.compile(r"\(cid:\d+\)")
_WINANSA = set(
    "\u2020\u2021\u00f7\u00a9\u00ff\u00d0\u00d7\u00de\u00df\u00f0\u00fe\u00e6\u0153\u0152"
)


def _is_corrupted(text: str) -> bool:
    """True if text contains legacy-font artefacts (control chars / CID / WinAnsi)."""
    ctrl = sum(1 for ch in text if 0 < ord(ch) < 32 and ch not in "\t\n\r")
    return ctrl > 5 or bool(_CID_RE.search(text)) or any(ch in _WINANSA for ch in text)


def _clean(text: str) -> str:
    """Strip control chars and CID refs so the display at least readable."""
    text = _CID_RE.sub("", text)
    text = "".join(ch if (ch >= " " or ch in "\t\n\r") else "" for ch in text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sanitize_for_display(obj):
    """Recursively clean all strings in a result dict for display."""
    if isinstance(obj, str):
        return _clean(obj)
    if isinstance(obj, list):
        return [_sanitize_for_display(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_for_display(v) for k, v in obj.items()}
    return obj


def _render_sidebar_decisions(pdf_results: dict) -> None:
    """Render per-PDF decision log panels in the sidebar."""
    _SEV_ICON = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}

    for fname, rdict in pdf_results.items():
        doc = rdict.get("document", {})
        dsummary = doc.get("decision_summary", {})
        all_dec = doc.get("all_decisions", [])

        with st.expander(f"📄 {fname}", expanded=False):
            if not all_dec:
                st.caption("No decisions recorded.")
                continue

            # Severity counters
            by_sev = dsummary.get("by_severity", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("ℹ️ Info", by_sev.get("info", 0))
            c2.metric("⚠️ Warn", by_sev.get("warning", 0))
            c3.metric("❌ Error", by_sev.get("error", 0))

            # Keyword chips
            keywords = dsummary.get("unique_keywords", [])
            if keywords:
                st.caption(" · ".join(f"`{k}`" for k in keywords))

            st.divider()

            # Per-page decision breakdown
            pages_seen = sorted(set(d["page"] for d in all_dec))
            for pg in pages_seen:
                pg_decs = [d for d in all_dec if d["page"] == pg]
                non_info = sum(1 for d in pg_decs if d["severity"] != "info")
                tag = f"  ⚠️ {non_info}" if non_info else ""
                with st.expander(
                    f"Page {pg}  ({len(pg_decs)} decisions{tag})", expanded=False
                ):
                    for d in pg_decs:
                        icon = _SEV_ICON.get(d["severity"], "•")
                        st.write(f"{icon} `{d['keyword']}` — {d['detail']}")


def main():
    st.set_page_config(
        page_title="Last-Try OCR — Bangla + English",
        page_icon="📄",
        layout="wide",
    )

    st.title("📄 Last-Try OCR System")
    st.caption("Government-grade hybrid OCR for Bangla + English PDFs")

    # Persist processed results across reruns for sidebar decision log
    if "pdf_results" not in st.session_state:
        st.session_state.pdf_results = {}  # filename → result_dict

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        use_mp = st.checkbox("Enable Multiprocessing", value=True)

        # Service Status Section
        st.divider()
        st.subheader("🔌 Service Status")
        service_status = get_service_status()

        # Gemini status
        gemini_available = service_status.get("gemini_available")
        gemini_error = service_status.get("gemini_error", "")
        if gemini_available is True:
            st.success("✅ Gemini API: Online")
        elif gemini_available is False:
            st.error("❌ Gemini API: Unavailable")
            if gemini_error:
                st.caption(
                    f"_{gemini_error[:80]}_"
                    if len(str(gemini_error)) > 80
                    else f"_{gemini_error}_"
                )
        else:
            st.info("⏳ Gemini: Not checked yet")

        # Ollama status
        ollama_available = service_status.get("ollama_available")
        ollama_error = service_status.get("ollama_error", "")
        ollama_model = service_status.get("ollama_model", "")
        if ollama_available is True:
            st.success(f"✅ Ollama: {ollama_model}")
        elif ollama_available is False:
            st.warning("⚠️ Ollama: Not running")
            if ollama_error:
                if "Cannot connect" in str(ollama_error):
                    st.caption("_Run `ollama serve` to start_")
                else:
                    st.caption(
                        f"_{ollama_error[:60]}_"
                        if len(str(ollama_error)) > 60
                        else f"_{ollama_error}_"
                    )
        else:
            st.info("⏳ Ollama: Not checked yet")

        # Show API stats only if there were actual calls
        stats = get_api_stats()
        if stats["total_calls"] > 0 or stats["errors"] > 0:
            st.divider()
            st.subheader("📊 API Usage")
            col1, col2 = st.columns(2)
            col1.metric("Gemini", stats.get("gemini_calls", 0))
            col2.metric("Ollama", stats.get("ollama_calls", 0))
            if stats["gemini_tokens"] > 0:
                st.caption(f"Tokens: {stats['gemini_tokens']:,}")
            if stats["errors"] > 0:
                st.error(f"Errors: {stats['errors']}")
            if st.button("Reset Stats"):
                reset_api_stats()
                st.rerun()

        # Decision log — stays populated across reruns via session_state
        if st.session_state.pdf_results:
            st.divider()
            st.subheader("🔍 Processing Decisions")
            _render_sidebar_decisions(st.session_state.pdf_results)

    # File upload
    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("🚀 Process PDFs", type="primary"):
        reset_api_stats()

        for upload_file in uploaded_files:
            st.divider()
            st.subheader(f"📎 {upload_file.name}")

            with st.spinner(f"Processing {upload_file.name}..."):
                # Save to temp
                tmp_dir = tempfile.mkdtemp()
                tmp_path = os.path.join(tmp_dir, upload_file.name)

                try:
                    with open(tmp_path, "wb") as f:
                        f.write(upload_file.getbuffer())

                    doc_result = process_pdf(tmp_path, use_multiprocessing=use_mp)
                    result_dict = _sanitize_for_display(doc_result.to_dict())

                    # Persist for sidebar decision log
                    st.session_state.pdf_results[upload_file.name] = result_dict

                    # Summary
                    doc_meta = result_dict["document"]
                    summary = doc_meta["processing_summary"]

                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Pages", doc_meta["total_pages"])
                    col2.metric("Languages", ", ".join(doc_meta["language_detected"]))
                    col3.metric("Confidence", f"{summary['overall_confidence']:.2%}")
                    col4.metric("API Pages", summary["pages_sent_to_api"])
                    proc_time = summary.get("processing_time_ms", 0)
                    if proc_time > 1000:
                        col5.metric("Time", f"{proc_time / 1000:.1f}s")
                    else:
                        col5.metric("Time", f"{proc_time:.0f}ms")

                    # Processing Summary Box
                    api_stats = get_api_stats()
                    summary_parts = []

                    # Determine what engines were used
                    pages_digital = sum(
                        1
                        for p in result_dict["pages"]
                        if p.get("extraction", {}).get("method") == "digital"
                    )
                    pages_local_ocr = sum(
                        1
                        for p in result_dict["pages"]
                        if p.get("extraction", {}).get("engine")
                        in ("EasyOCR", "PaddleOCR")
                    )
                    pages_api = summary.get("pages_sent_to_api", 0)

                    if pages_digital > 0:
                        summary_parts.append(
                            f"**{pages_digital}** pages extracted digitally (fast)"
                        )
                    if pages_local_ocr > 0:
                        summary_parts.append(
                            f"**{pages_local_ocr}** pages used local OCR"
                        )

                    if api_stats["gemini_calls"] > 0:
                        summary_parts.append(
                            f"**{api_stats['gemini_calls']}** Gemini API calls"
                        )
                    if api_stats["ollama_calls"] > 0:
                        summary_parts.append(
                            f"**{api_stats['ollama_calls']}** Ollama calls"
                        )

                    if (
                        pages_api == 0
                        and api_stats["gemini_calls"] == 0
                        and api_stats["ollama_calls"] == 0
                    ):
                        summary_parts.append(
                            "No API calls needed - all text extracted locally"
                        )

                    if api_stats["errors"] > 0:
                        summary_parts.append(f"⚠️ {api_stats['errors']} API errors")

                    # Show summary in an info box
                    if summary_parts:
                        st.info(
                            "📊 **Processing Summary:** " + " · ".join(summary_parts)
                        )

                    # Tabs for each page
                    if result_dict["pages"]:
                        tabs = st.tabs(
                            [f"Page {p['page_number']}" for p in result_dict["pages"]]
                        )
                        for tab, page_data in zip(tabs, result_dict["pages"]):
                            with tab:
                                _render_page(page_data)

                    # Full JSON
                    with st.expander("📋 Full JSON Output"):
                        st.json(result_dict)

                except Exception as e:
                    st.error(f"Error processing {upload_file.name}: {e}")
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)


def _render_page(page_data: dict):
    """Render a single page's results."""
    ext = page_data["extraction"]

    # Engine badge with color
    engine = ext.get("engine", "unknown")
    engine_badge = {
        "PyMuPDF": "🟢 PyMuPDF (Digital)",
        "EasyOCR": "🟡 EasyOCR (Local)",
        "PaddleOCR": "🟡 PaddleOCR (Local)",
        "Gemini": "🔵 Gemini (API)",
        "Ollama": "🟣 Ollama (Local LLM)",
    }.get(engine, f"⚪ {engine}")

    # Extraction info
    st.caption(
        f"Engine: **{engine_badge}** | Method: **{ext['method']}** | "
        f"Confidence: **{ext['confidence_score']:.2%}** | "
        f"Correction: {'✅' if ext['correction_applied'] else '—'} | "
        f"Numerics OK: {'✅' if ext['numeric_validation_passed'] else '⚠️'}"
    )

    # Corruption detection — check full_text and first few blocks
    sample_text = page_data.get("full_text", "")
    if not sample_text and page_data.get("content_blocks"):
        sample_text = " ".join(
            b.get("text", "") for b in page_data["content_blocks"][:3]
        )
    if _is_corrupted(sample_text):
        st.warning(
            "⚠️ **Legacy font encoding detected** — this page was extracted from a "
            "PDF using a custom Bangla font (e.g. SutonnyMJ / BijoyBaijra). "
            "The text shown below has been cleaned but may still be incomplete. "
            "Enable **API fallback** and re-process for full Bangla Unicode output."
        )

    # Content blocks
    if page_data.get("content_blocks"):
        st.markdown("**Content Blocks:**")
        for block in page_data["content_blocks"]:
            lang_badge = {"bn": "🇧🇩", "en": "🇬🇧", "mixed": "🌐"}.get(
                block["language"], ""
            )
            with st.container():
                st.markdown(
                    f"**Block {block['block_id']}** {lang_badge} "
                    f"[{block['type']}] (conf: {block['confidence']:.2f})"
                )
                st.text(block["text"])

    # Tables
    if page_data.get("tables"):
        st.markdown("**Tables:**")
        for table in page_data["tables"]:
            st.caption(
                f"Table {table['table_id']} "
                f"(structure conf: {table['structure_confidence']:.2f})"
            )
            if table["rows"]:
                st.table(table["rows"])

    # Images
    if page_data.get("images"):
        st.markdown("**Images:**")
        for img in page_data["images"]:
            st.caption(
                f"Image {img['image_id']} [{img['type']}] "
                f"(conf: {img['confidence']:.2f})"
            )
            st.text(img["description"])
            if img.get("detected_text"):
                st.code(img["detected_text"], language=None)

    # Full text
    if page_data.get("full_text"):
        with st.expander("Full Text"):
            st.text(page_data["full_text"])

    # Decision log for this page
    page_decisions = page_data.get("decisions", [])
    if page_decisions:
        _SEV_ICON = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}
        with st.expander(
            f"🧠 Decision Log ({len(page_decisions)} decisions)", expanded=False
        ):
            for d in page_decisions:
                icon = _SEV_ICON.get(d.get("severity", "info"), "•")
                st.write(f"{icon} `{d['keyword']}` — {d['detail']}")


if __name__ == "__main__":
    main()
