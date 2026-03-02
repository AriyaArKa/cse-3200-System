"""
DocuCard — Demo Card Viewer (Streamlit)
Browse all 5 card templates with live HTML preview.
Run: streamlit run demo_viewer.py
"""

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="DocuCard — Demo Cards",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme override ──
st.markdown(
    """
<style>
    .stApp { background-color: #0f1117; }
    [data-testid="stSidebar"] { background-color: #1a1b23; }
    .card-frame { 
        border: 1px solid rgba(255,255,255,0.08); 
        border-radius: 12px; 
        overflow: hidden;
        background: #1a1b23;
    }
    .card-frame iframe {
        border: none;
        width: 100%;
        min-height: 800px;
    }
    .gallery-card {
        background: #1a1b23;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: all 0.2s;
    }
    .gallery-card:hover {
        border-color: rgba(255,255,255,0.15);
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Card definitions ──
CARDS = [
    {
        "id": "01",
        "icon": "🎓",
        "title": "Student Support Card",
        "subtitle": "University Notices",
        "file": "01_student_support_card.html",
        "color": "#3b82f6",
        "desc": "Extracts key actions, deadlines, and affected groups from university notices.",
        "social": "Students waste hours reading complex notices. This card tells you exactly what to do in 30 seconds.",
    },
    {
        "id": "02",
        "icon": "💼",
        "title": "Job Eligibility Checker",
        "subtitle": "Job Circulars",
        "file": "02_job_eligibility_card.html",
        "color": "#22c55e",
        "desc": "Checks if you qualify for a job based on age, education, and experience.",
        "social": "Job seekers waste days decoding 10-page circulars. This card checks eligibility instantly.",
    },
    {
        "id": "03",
        "icon": "🏛️",
        "title": "Government Policy Impact",
        "subtitle": "Government Circulars",
        "file": "03_government_policy_card.html",
        "color": "#f59e0b",
        "desc": "Translates dense government orders into plain language with before/after views.",
        "social": "Government orders are in complex legal language. This card makes them instantly clear.",
    },
    {
        "id": "04",
        "icon": "🏦",
        "title": "Financial Health Card",
        "subtitle": "Bank Statements",
        "file": "04_financial_health_card.html",
        "color": "#06b6d4",
        "desc": "Analyzes spending patterns, risk alerts, and personalized savings suggestions.",
        "social": "Most people never read their bank statements. This card reveals hidden financial risks.",
    },
    {
        "id": "05",
        "icon": "📋",
        "title": "Meeting Decision Tracker",
        "subtitle": "Meeting Minutes",
        "file": "05_meeting_tracker_card.html",
        "color": "#a855f7",
        "desc": "Converts meeting minutes into tracked decisions with owners and deadlines.",
        "social": "Meetings generate decisions, but nobody tracks them. This card ensures accountability.",
    },
]

DEMO_DIR = Path(__file__).parent / "demo_cards"


def load_card_html(filename: str) -> str | None:
    """Load HTML content from demo_cards folder."""
    path = DEMO_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def inject_base_tag(html: str) -> str:
    """
    For Streamlit iframe rendering, we need to inline the CSS
    since relative paths don't work inside st.components.html.
    """
    css_path = DEMO_DIR / "shared_styles.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        # Replace the <link rel="stylesheet" href="shared_styles.css"> with inline <style>
        html = html.replace(
            '<link rel="stylesheet" href="shared_styles.css">',
            f"<style>\n{css}\n</style>",
        )
    return html


# ── Sidebar ──
with st.sidebar:
    st.markdown("## 📄 DocuCard")
    st.markdown("##### AI Document Intelligence")
    st.divider()

    view_mode = st.radio(
        "View Mode",
        ["🔍 Single Card", "📊 Gallery Overview"],
        index=0,
        label_visibility="collapsed",
    )

    if view_mode == "🔍 Single Card":
        st.divider()
        st.markdown("##### Select Card Template")
        selected_idx = 0
        for i, card in enumerate(CARDS):
            if st.button(
                f"{card['icon']}  {card['title']}",
                key=f"card_{i}",
                use_container_width=True,
                type=(
                    "primary"
                    if i == st.session_state.get("selected", 0)
                    else "secondary"
                ),
            ):
                st.session_state["selected"] = i
        selected_idx = st.session_state.get("selected", 0)

    st.divider()
    st.markdown(
        "<div style='font-size:11px;color:#666;text-align:center;'>"
        "CSE-3200 System Project<br>KUET 2025</div>",
        unsafe_allow_html=True,
    )


# ── Main Content ──
if view_mode == "🔍 Single Card":
    selected = CARDS[st.session_state.get("selected", 0)]

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {selected['icon']} {selected['title']}")
        st.caption(selected["desc"])
    with col2:
        st.markdown(
            f"<div style='text-align:right;padding:10px;background:rgba(255,255,255,0.03);"
            f"border-radius:8px;border-left:3px solid {selected['color']};'>"
            f"<span style='font-size:12px;color:#888;'>PDF Type</span><br>"
            f"<span style='font-size:14px;font-weight:600;'>{selected['subtitle']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Social value
    st.info(f"💡 {selected['social']}")

    # Render card
    html = load_card_html(selected["file"])
    if html:
        html = inject_base_tag(html)
        st.components.v1.html(html, height=900, scrolling=True)
    else:
        st.error(f"Card file not found: {selected['file']}")

else:
    # Gallery mode
    st.markdown("## 📊 All Card Templates")
    st.caption("Click a card in the sidebar to view it in detail")

    cols = st.columns(3)
    for i, card in enumerate(CARDS):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="background:#1a1b23;border:1px solid rgba(255,255,255,0.08);
                border-radius:12px;padding:24px;margin-bottom:16px;
                border-top:3px solid {card['color']};">
                    <div style="font-size:32px;margin-bottom:8px;">{card['icon']}</div>
                    <div style="font-size:16px;font-weight:700;margin-bottom:6px;">{card['title']}</div>
                    <div style="font-size:12px;color:#a0a0b0;margin-bottom:12px;">{card['desc']}</div>
                    <div style="font-size:11px;color:#666;padding:10px;background:rgba(255,255,255,0.03);
                    border-radius:6px;border-left:2px solid {card['color']};">
                        💡 {card['social']}
                    </div>
                    <div style="margin-top:12px;font-size:11px;color:#666;">
                        PDF Type: <strong style="color:#a0a0b0;">{card['subtitle']}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # Quick preview section
    st.markdown("### Quick Preview")
    preview_choice = st.selectbox(
        "Select card to preview",
        options=[c["title"] for c in CARDS],
        label_visibility="collapsed",
    )
    chosen = next(c for c in CARDS if c["title"] == preview_choice)
    html = load_card_html(chosen["file"])
    if html:
        html = inject_base_tag(html)
        st.components.v1.html(html, height=800, scrolling=True)
