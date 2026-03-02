"""
Streamlit frontend for the Gemini OCR Document Processing System.
Run:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import time

import pandas as pd
import requests
import streamlit as st

# ──────────────────────────── Config ─────────────────────────────────────

API_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{API_URL}/upload-pdf"
HEALTH_ENDPOINT = f"{API_URL}/health"

# ──────────────────────────── Page setup ─────────────────────────────────

st.set_page_config(
    page_title="Gemini OCR System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Custom CSS ─────────────────────────────────

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    .stAlert { border-radius: 8px; }
    .metric-card {
        background: #1e1e2f;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
        border: 1px solid #333;
    }
    .doc-type-badge {
        display: inline-block;
        background: #4f46e5;
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .flag-box {
        background: #3b1a1a;
        border-left: 4px solid #ef4444;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.9rem;
    }
    .confidence-high { color: #22c55e; font-weight: 700; }
    .confidence-med  { color: #f59e0b; font-weight: 700; }
    .confidence-low  { color: #ef4444; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────── Sidebar ────────────────────────────────────

with st.sidebar:
    st.title("📄 Gemini OCR")
    st.caption("Powered by Google Gemini Vision")
    st.divider()

    # API health
    try:
        resp = requests.get(HEALTH_ENDPOINT, timeout=3)
        if resp.status_code == 200:
            st.success("✅ API Server: Online")
        else:
            st.error("❌ API Server: Unhealthy")
    except Exception:
        st.error(
            "❌ API Server: Offline\n\nStart it with:\n```\nuvicorn app.main:app --port 8000\n```"
        )

    st.divider()
    st.markdown("**Settings**")
    show_raw_json = st.toggle("Show raw JSON response", value=False)
    show_raw_text = st.toggle("Show raw page text", value=True)
    confidence_threshold = st.slider("Confidence threshold", 0.0, 1.0, 0.85, 0.05)

    st.divider()
    st.markdown(
        "**Supported document types**\n"
        "- 🧾 Invoices & receipts\n"
        "- 🏛️ Government notices\n"
        "- 📋 Forms\n"
        "- 📊 Tables\n"
        "- 📝 Reports & letters\n"
        "- 🔍 Scanned PDFs"
    )

# ──────────────────────────── Main area ──────────────────────────────────

st.title("📄 Gemini OCR — Document Intelligence")
st.markdown("Upload any PDF and receive structured, machine-readable JSON output.")

uploaded_file = st.file_uploader(
    "Drop your PDF here",
    type=["pdf"],
    help="Max 50 MB. Multi-page PDFs are fully supported.",
)

if uploaded_file is not None:
    col1, col2, col3 = st.columns(3)
    col1.metric("File name", uploaded_file.name)
    col2.metric("File size", f"{len(uploaded_file.getvalue()) / 1024:.1f} KB")
    col3.metric("Type", uploaded_file.type or "application/pdf")

    st.divider()

    if st.button("🚀 Process PDF", type="primary", use_container_width=True):
        with st.spinner(
            "Converting PDF pages and running Gemini OCR… this may take a moment."
        ):
            t0 = time.time()
            try:
                files = {
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        "application/pdf",
                    )
                }
                response = requests.post(UPLOAD_ENDPOINT, files=files, timeout=300)
                elapsed = time.time() - t0
            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Cannot connect to the API server. Make sure it is running on port 8000."
                )
                st.stop()
            except requests.exceptions.Timeout:
                st.error("❌ Request timed out (300 s). Try a smaller PDF.")
                st.stop()

        # ── Parse response ──────────────────────────────────────────────
        if response.status_code == 200:
            payload = response.json()
        else:
            st.error(f"API error {response.status_code}: {response.text}")
            st.stop()

        if not payload.get("success"):
            st.error(f"Processing failed: {payload.get('error', 'Unknown error')}")
            st.stop()

        data = payload["data"]
        flags = payload.get("validation_flags", [])

        # ── Summary bar ────────────────────────────────────────────────
        st.success(f"✅ Processing complete in **{elapsed:.1f}s**")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Document type", data["document_type"].replace("_", " ").title())
        m2.metric("Total pages", data["total_pages"])
        avg_conf = (
            sum(p["confidence_score"] for p in data["pages"]) / len(data["pages"])
            if data["pages"]
            else 0
        )
        m3.metric("Avg confidence", f"{avg_conf:.0%}")
        m4.metric("Validation flags", len(flags))

        # ── Validation flags ───────────────────────────────────────────
        if flags:
            with st.expander(f"⚠️ {len(flags)} Validation Flag(s)", expanded=True):
                for f in flags:
                    st.markdown(
                        f'<div class="flag-box">'
                        f'<strong>Page {f["page_number"]}</strong> — '
                        f'<code>{f["issue"]}</code><br>{f["details"]}'
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        st.divider()

        # ── Per-page results ───────────────────────────────────────────
        pages = data["pages"]
        tab_labels = [f"Page {p['page_number']}" for p in pages]
        tabs = st.tabs(tab_labels) if len(pages) > 1 else [st.container()]

        for tab, page in zip(tabs, pages):
            with tab:
                # Confidence badge
                score = page["confidence_score"]
                if score >= 0.85:
                    conf_class = "confidence-high"
                elif score >= 0.60:
                    conf_class = "confidence-med"
                else:
                    conf_class = "confidence-low"

                st.markdown(
                    f'Confidence: <span class="{conf_class}">{score:.0%}</span>',
                    unsafe_allow_html=True,
                )

                # ── Raw text ─────────────────────────────────────────
                if show_raw_text and page.get("raw_text"):
                    with st.expander("📝 Raw extracted text", expanded=False):
                        st.text(page["raw_text"])

                # ── Key-value pairs ──────────────────────────────────
                if page.get("key_value_pairs"):
                    st.subheader("🔑 Key-Value Pairs")
                    kv = page["key_value_pairs"]
                    kv_df = pd.DataFrame(list(kv.items()), columns=["Field", "Value"])
                    st.dataframe(kv_df, use_container_width=True, hide_index=True)

                # ── Tables ───────────────────────────────────────────
                if page.get("tables"):
                    st.subheader(f"📊 Tables ({len(page['tables'])} found)")
                    for i, tbl in enumerate(page["tables"], 1):
                        st.markdown(f"**Table {i}**")
                        if tbl["headers"] and tbl["rows"]:
                            df = pd.DataFrame(tbl["rows"], columns=tbl["headers"])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        elif tbl["rows"]:
                            df = pd.DataFrame(tbl["rows"])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Empty table detected.")

                # ── Line items ───────────────────────────────────────
                if page.get("line_items"):
                    st.subheader(f"🧾 Line Items ({len(page['line_items'])} rows)")
                    li_data = [
                        {
                            "Description": li["description"],
                            "Quantity": li["quantity"],
                            "Unit Price": li["unit_price"],
                            "Total": li["total"],
                        }
                        for li in page["line_items"]
                    ]
                    li_df = pd.DataFrame(li_data)
                    st.dataframe(li_df, use_container_width=True, hide_index=True)

                    # Computed total
                    computed = page.get("key_value_pairs", {}).get(
                        "computed_line_items_total"
                    )
                    if computed:
                        st.info(f"💰 Computed line items total: **{computed}**")

                # ── Nothing found ────────────────────────────────────
                if (
                    not page.get("key_value_pairs")
                    and not page.get("tables")
                    and not page.get("line_items")
                ):
                    st.warning("No structured data extracted from this page.")

        # ── Raw JSON ──────────────────────────────────────────────────
        if show_raw_json:
            st.divider()
            st.subheader("🗂️ Raw JSON Response")
            st.json(payload)

        # ── Download button ───────────────────────────────────────────
        st.divider()
        st.download_button(
            label="⬇️ Download JSON result",
            data=json.dumps(payload, indent=2, ensure_ascii=False),
            file_name=f"{uploaded_file.name.replace('.pdf', '')}_ocr_result.json",
            mime="application/json",
            use_container_width=True,
        )

else:
    # Landing state
    st.info("👆 Upload a PDF using the file picker above to get started.")

    with st.expander("📖 How it works"):
        st.markdown(
            """
            1. **Upload** any PDF (invoices, forms, government docs, scanned pages)
            2. The system converts each page to a **300 DPI image**
            3. Each image is sent to **Google Gemini Vision** for OCR + layout analysis
            4. Gemini returns **strict JSON** with tables, key-value pairs, and line items
            5. Post-processing **validates totals**, normalises dates, and flags low-confidence pages
            6. You see all structured data here — and can **download the JSON**
            """
        )
