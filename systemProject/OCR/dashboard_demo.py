"""
DocuCard — Dashboard Demo (Streamlit)
Full NotebookLM-style flow: Upload → Process → Classify → Card Select → View

Run: streamlit run dashboard_demo.py
"""

import streamlit as st
import time
import json
import random
from pathlib import Path

# ── Page config ──
st.set_page_config(
    page_title="DocuCard — Dashboard",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ──
DEMO_DIR = Path(__file__).parent / "demo_cards"

PDF_TYPES = {
    "PDF001": {"category": "University Notice", "icon": "🎓", "color": "#3b82f6"},
    "PDF002": {"category": "Government Circular", "icon": "🏛️", "color": "#f59e0b"},
    "PDF003": {"category": "Job Circular", "icon": "💼", "color": "#22c55e"},
    "PDF004": {"category": "Financial Document", "icon": "🏦", "color": "#06b6d4"},
    "PDF005": {"category": "Meeting Minutes", "icon": "📋", "color": "#a855f7"},
}

CARDS = [
    {
        "id": "student_support_card",
        "name": "Student Action & Support Card",
        "icon": "🎓",
        "color": "#3b82f6",
        "pdf_type": "PDF001",
        "desc": "Extracts actions, deadlines, affected groups from university notices",
        "social": "Students waste hours reading complex notices. Get answers in 30 seconds.",
        "file": "01_student_support_card.html",
        "sections": [
            "What Is This About?",
            "Who Is Affected?",
            "What You Must Do",
            "Important Deadlines",
            "Risk If Ignored",
        ],
    },
    {
        "id": "job_eligibility_checker_card",
        "name": "Job Eligibility & Preparation Card",
        "icon": "💼",
        "color": "#22c55e",
        "pdf_type": "PDF003",
        "desc": "Checks if you qualify and shows step-by-step application process",
        "social": "Job seekers waste days decoding 10-page circulars. Check eligibility instantly.",
        "file": "02_job_eligibility_card.html",
        "sections": [
            "Job Overview",
            "Eligibility Checklist",
            "Documents Required",
            "Application Steps",
            "Deadline & Countdown",
        ],
    },
    {
        "id": "government_policy_impact_card",
        "name": "Government Policy Impact Card",
        "icon": "🏛️",
        "color": "#f59e0b",
        "pdf_type": "PDF002",
        "desc": "Translates complex government orders into plain language",
        "social": "Government orders are in legal language. See what actually changes for you.",
        "file": "03_government_policy_card.html",
        "sections": [
            "Policy Summary",
            "Who Is Impacted?",
            "What Changes?",
            "Action Needed?",
            "Effective Date",
        ],
    },
    {
        "id": "financial_health_card",
        "name": "Personal Financial Health Card",
        "icon": "🏦",
        "color": "#06b6d4",
        "pdf_type": "PDF004",
        "desc": "Analyzes spending patterns, risk alerts, and savings suggestions",
        "social": "Most people never read bank statements. Discover hidden financial risks.",
        "file": "04_financial_health_card.html",
        "sections": [
            "Monthly Summary",
            "Spending Pattern",
            "Risk Alert",
            "Savings Suggestions",
        ],
    },
    {
        "id": "meeting_decision_tracker_card",
        "name": "Meeting Decision & Responsibility Tracker",
        "icon": "📋",
        "color": "#a855f7",
        "pdf_type": "PDF005",
        "desc": "Tracks decisions with owners, deadlines, and follow-up reminders",
        "social": "Meetings generate decisions, but nobody tracks them. Ensure accountability.",
        "file": "05_meeting_tracker_card.html",
        "sections": [
            "Meeting Summary",
            "Decisions Taken",
            "Responsibility Table",
            "Follow-Up Reminder",
        ],
    },
]

# Demo PDF data for simulation
DEMO_PDFS = {
    "ছুটি_ঘোষণা_বিজ্ঞপ্তি.pdf": {
        "pages": 1,
        "size": "84 KB",
        "detected_type": "PDF001",
        "confidence": 94,
        "match_scores": {
            "student_support_card": 94,
            "job_eligibility_checker_card": 8,
            "government_policy_impact_card": 22,
            "financial_health_card": 3,
            "meeting_decision_tracker_card": 12,
        },
    },
    "bangladesh_bank_circular.pdf": {
        "pages": 3,
        "size": "215 KB",
        "detected_type": "PDF003",
        "confidence": 91,
        "match_scores": {
            "student_support_card": 10,
            "job_eligibility_checker_card": 91,
            "government_policy_impact_card": 18,
            "financial_health_card": 5,
            "meeting_decision_tracker_card": 8,
        },
    },
    "salary_revision_order.pdf": {
        "pages": 2,
        "size": "156 KB",
        "detected_type": "PDF002",
        "confidence": 87,
        "match_scores": {
            "student_support_card": 5,
            "job_eligibility_checker_card": 12,
            "government_policy_impact_card": 87,
            "financial_health_card": 15,
            "meeting_decision_tracker_card": 10,
        },
    },
    "dbbl_monthly_statement.pdf": {
        "pages": 4,
        "size": "340 KB",
        "detected_type": "PDF004",
        "confidence": 89,
        "match_scores": {
            "student_support_card": 3,
            "job_eligibility_checker_card": 5,
            "government_policy_impact_card": 8,
            "financial_health_card": 89,
            "meeting_decision_tracker_card": 6,
        },
    },
    "cse_dept_meeting_minutes.pdf": {
        "pages": 2,
        "size": "98 KB",
        "detected_type": "PDF005",
        "confidence": 85,
        "match_scores": {
            "student_support_card": 15,
            "job_eligibility_checker_card": 5,
            "government_policy_impact_card": 20,
            "financial_health_card": 4,
            "meeting_decision_tracker_card": 85,
        },
    },
}


# ──────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────
st.markdown(
    """
<style>
    /* Base */
    .stApp { background: #0f1117; }
    [data-testid="stSidebar"] { background: #13141b; }
    
    /* Upload area */
    .upload-zone {
        border: 2px dashed rgba(59,130,246,0.3);
        border-radius: 16px;
        padding: 60px 40px;
        text-align: center;
        background: rgba(59,130,246,0.03);
        margin: 20px 0;
        transition: all 0.3s;
    }
    .upload-zone:hover {
        border-color: rgba(59,130,246,0.6);
        background: rgba(59,130,246,0.06);
    }
    
    /* Card selector grid */
    .card-selector {
        background: #1a1b23;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s;
        min-height: 220px;
    }
    .card-selector:hover {
        border-color: rgba(255,255,255,0.2);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .card-selector.recommended {
        border-color: rgba(59,130,246,0.5);
        background: rgba(59,130,246,0.05);
        box-shadow: 0 0 20px rgba(59,130,246,0.1);
    }
    
    /* Score bar */
    .score-bar-bg {
        width: 100%;
        height: 6px;
        background: rgba(255,255,255,0.06);
        border-radius: 3px;
        margin: 8px 0;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.5s ease;
    }
    
    /* Confidence badge */
    .conf-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .conf-high { background: rgba(34,197,94,0.15); color: #22c55e; }
    .conf-mid { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .conf-low { background: rgba(239,68,68,0.15); color: #ef4444; }
    
    /* PDF file card */
    .pdf-card {
        background: #1a1b23;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .pdf-card:hover { border-color: rgba(255,255,255,0.15); }
    .pdf-card.active { border-color: rgba(59,130,246,0.5); background: rgba(59,130,246,0.05); }
    
    /* Phase indicator */
    .phase-bar {
        display: flex;
        gap: 0;
        margin: 20px 0 30px;
    }
    .phase-step {
        flex: 1;
        text-align: center;
        padding: 12px 8px;
        font-size: 12px;
        font-weight: 600;
        position: relative;
        color: #666;
    }
    .phase-step.active {
        color: #3b82f6;
    }
    .phase-step.done {
        color: #22c55e;
    }
    .phase-line {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: rgba(255,255,255,0.06);
        border-radius: 2px;
    }
    .phase-line.active { background: #3b82f6; }
    .phase-line.done { background: #22c55e; }
    
    /* Warning box */
    .warn-box {
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        margin: 10px 0;
        border-left: 3px solid;
    }
    .warn-box.warn { background: rgba(245,158,11,0.08); border-color: #f59e0b; color: #f59e0b; }
    .warn-box.error { background: rgba(239,68,68,0.08); border-color: #ef4444; color: #ef4444; }
    .warn-box.success { background: rgba(34,197,94,0.08); border-color: #22c55e; color: #22c55e; }
    .warn-box.info { background: rgba(59,130,246,0.08); border-color: #3b82f6; color: #3b82f6; }
    
    /* Section cards inside card view */
    .section-card {
        background: #1a1b23;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .section-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .section-title-text {
        font-size: 14px;
        font-weight: 600;
        color: #e8e8ed;
    }
    .tag-sm {
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 500;
    }
    .tag-ai { background: rgba(168,85,247,0.15); color: #a855f7; }
    .tag-edit { background: rgba(59,130,246,0.15); color: #3b82f6; }
    .tag-regen { background: rgba(34,197,94,0.15); color: #22c55e; }
    
    /* Hide streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────
# Session state initialization
# ──────────────────────────────────────────
if "phase" not in st.session_state:
    st.session_state.phase = "upload"  # upload | processing | dashboard | card_view
if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = {}  # filename -> pdf data
if "active_pdf" not in st.session_state:
    st.session_state.active_pdf = None
if "selected_card" not in st.session_state:
    st.session_state.selected_card = None
if "use_demo_data" not in st.session_state:
    st.session_state.use_demo_data = False


def set_phase(phase):
    st.session_state.phase = phase


def select_pdf(name):
    st.session_state.active_pdf = name
    st.session_state.selected_card = None
    st.session_state.phase = "dashboard"


def select_card(card_id):
    st.session_state.selected_card = card_id
    st.session_state.phase = "card_view"


def back_to_dashboard():
    st.session_state.selected_card = None
    st.session_state.phase = "dashboard"


def reset_all():
    st.session_state.phase = "upload"
    st.session_state.uploaded_pdfs = {}
    st.session_state.active_pdf = None
    st.session_state.selected_card = None
    st.session_state.use_demo_data = False


def load_card_html(filename):
    css_path = DEMO_DIR / "shared_styles.css"
    card_path = DEMO_DIR / filename
    if not card_path.exists():
        return None
    html = card_path.read_text(encoding="utf-8")
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        html = html.replace(
            '<link rel="stylesheet" href="shared_styles.css">',
            f"<style>\n{css}\n</style>",
        )
    return html


def conf_class(score):
    if score >= 80:
        return "conf-high"
    elif score >= 50:
        return "conf-mid"
    return "conf-low"


def conf_label(score):
    if score >= 80:
        return "High Match"
    elif score >= 50:
        return "Partial Match"
    return "Low Match"


# ──────────────────────────────────────────
# Phase indicator bar
# ──────────────────────────────────────────
def render_phase_bar():
    phases = [
        ("📤 Upload", "upload"),
        ("🤖 Process", "processing"),
        ("📊 Dashboard", "dashboard"),
        ("📋 Card View", "card_view"),
    ]
    phase_order = ["upload", "processing", "dashboard", "card_view"]
    current_idx = phase_order.index(st.session_state.phase)

    html = '<div class="phase-bar">'
    for i, (label, key) in enumerate(phases):
        if i < current_idx:
            cls = "done"
        elif i == current_idx:
            cls = "active"
        else:
            cls = ""
        html += f'<div class="phase-step {cls}">{label}<div class="phase-line {cls}"></div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ──────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📄 DocuCard")
    st.caption("AI Document Intelligence")
    st.divider()

    if (
        st.session_state.phase in ("dashboard", "card_view")
        and st.session_state.uploaded_pdfs
    ):
        st.markdown("##### 📁 Your Documents")
        for name, data in st.session_state.uploaded_pdfs.items():
            t = PDF_TYPES[data["detected_type"]]
            is_active = st.session_state.active_pdf == name
            cls = "active" if is_active else ""
            st.markdown(
                f"""<div class="pdf-card {cls}">
                    <div style="font-size:13px;font-weight:600;margin-bottom:4px;">{t['icon']} {name}</div>
                    <div style="font-size:11px;color:#888;">{t['category']} — {data['confidence']}%</div>
                    <div style="font-size:11px;color:#555;">{data['pages']} page(s) · {data['size']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(f"Select", key=f"sel_{name}", use_container_width=True):
                select_pdf(name)
                st.rerun()

        st.divider()

    if st.session_state.phase == "card_view":
        if st.button("← Back to Dashboard", use_container_width=True):
            back_to_dashboard()
            st.rerun()

    if st.session_state.phase != "upload":
        if st.button("🔄 Start Over", use_container_width=True, type="secondary"):
            reset_all()
            st.rerun()

    st.divider()
    st.markdown(
        "<div style='font-size:10px;color:#444;text-align:center;'>CSE-3200 System Project · KUET 2025</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════
# PHASE 1: UPLOAD
# ══════════════════════════════════════════
if st.session_state.phase == "upload":
    render_phase_bar()

    st.markdown("### 📤 Upload Your Documents")
    st.caption("Upload any PDF — Bangla, English, or mixed. We auto-detect the type.")

    # Upload zone
    uploaded_files = st.file_uploader(
        "Drop PDFs here",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("##### Or try with demo data")
    st.caption("Simulates 5 pre-processed PDFs (no API needed)")

    if st.button(
        "🎮 Load Demo Data (5 PDFs)", type="secondary", use_container_width=False
    ):
        st.session_state.uploaded_pdfs = dict(DEMO_PDFS)
        st.session_state.use_demo_data = True
        st.session_state.phase = "processing"
        st.rerun()

    if uploaded_files:
        st.markdown("##### Uploaded Files")
        for f in uploaded_files:
            st.markdown(
                f"""<div class="pdf-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <div style="font-size:13px;font-weight:600;">📄 {f.name}</div>
                            <div style="font-size:11px;color:#666;">{f.size / 1024:.1f} KB</div>
                        </div>
                        <div style="font-size:11px;color:#22c55e;">✅ Ready</div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

        if st.button("▶ Process All PDFs", type="primary", use_container_width=True):
            # For demo, simulate with random classification
            for f in uploaded_files:
                types = list(DEMO_PDFS.values())
                simulated = random.choice(types)
                st.session_state.uploaded_pdfs[f.name] = {
                    "pages": random.randint(1, 5),
                    "size": f"{f.size / 1024:.0f} KB",
                    "detected_type": simulated["detected_type"],
                    "confidence": simulated["confidence"],
                    "match_scores": dict(simulated["match_scores"]),
                }
            st.session_state.phase = "processing"
            st.rerun()


# ══════════════════════════════════════════
# PHASE 2: PROCESSING
# ══════════════════════════════════════════
elif st.session_state.phase == "processing":
    render_phase_bar()

    st.markdown("### 🤖 Processing Your Documents...")
    st.caption("AI is reading, extracting, and classifying each PDF")

    progress_container = st.container()

    with progress_container:
        for name, data in st.session_state.uploaded_pdfs.items():
            t = PDF_TYPES[data["detected_type"]]
            with st.status(f"Processing: {name}", expanded=True) as status:
                st.write("📄 Converting PDF to images...")
                time.sleep(0.3)

                st.write(f"🔍 Running OCR on {data['pages']} page(s)...")
                progress = st.progress(0)
                for i in range(data["pages"] if isinstance(data["pages"], int) else 1):
                    time.sleep(0.15)
                    progress.progress((i + 1) / max(data["pages"], 1))

                st.write("📦 Merging page data...")
                time.sleep(0.2)

                st.write(f"🏷️ Classifying document type...")
                time.sleep(0.3)

                status.update(
                    label=f"✅ {name} → {t['icon']} {t['category']} ({data['confidence']}%)",
                    state="complete",
                )

    st.success(f"✅ All {len(st.session_state.uploaded_pdfs)} documents processed!")

    # Summary table
    cols = st.columns(len(st.session_state.uploaded_pdfs))
    for i, (name, data) in enumerate(st.session_state.uploaded_pdfs.items()):
        t = PDF_TYPES[data["detected_type"]]
        with cols[i % len(cols)]:
            st.markdown(
                f"""<div style="background:#1a1b23;border:1px solid rgba(255,255,255,0.08);
                border-radius:10px;padding:16px;text-align:center;border-top:3px solid {t['color']};">
                    <div style="font-size:28px;margin-bottom:6px;">{t['icon']}</div>
                    <div style="font-size:12px;font-weight:600;margin-bottom:4px;">{name[:25]}{'...' if len(name)>25 else ''}</div>
                    <div style="font-size:11px;color:#888;margin-bottom:4px;">{t['category']}</div>
                    <div class="conf-badge {conf_class(data['confidence'])}">{data['confidence']}%</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("")
    if st.button("📊 Go to Dashboard →", type="primary", use_container_width=True):
        first = list(st.session_state.uploaded_pdfs.keys())[0]
        select_pdf(first)
        st.rerun()


# ══════════════════════════════════════════
# PHASE 3: DASHBOARD
# ══════════════════════════════════════════
elif st.session_state.phase == "dashboard":
    render_phase_bar()

    pdf_name = st.session_state.active_pdf
    if not pdf_name or pdf_name not in st.session_state.uploaded_pdfs:
        pdf_name = list(st.session_state.uploaded_pdfs.keys())[0]
        st.session_state.active_pdf = pdf_name

    pdf_data = st.session_state.uploaded_pdfs[pdf_name]
    detected = PDF_TYPES[pdf_data["detected_type"]]

    # Header
    st.markdown(f"### 📊 Dashboard — {pdf_name}")

    # PDF info bar
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Detected Type", detected["category"])
    with col2:
        st.metric("Confidence", f"{pdf_data['confidence']}%")
    with col3:
        st.metric("Pages", pdf_data["pages"])
    with col4:
        st.metric("File Size", pdf_data["size"])

    st.divider()

    # ── Card Selection ──
    st.markdown("### 🃏 Select a Card Template")
    st.caption("⭐ = AI recommended for this PDF type. You can select any card.")

    # Find recommended card
    recommended_id = None
    for c in CARDS:
        if c["pdf_type"] == pdf_data["detected_type"]:
            recommended_id = c["id"]
            break

    # Render card grid
    cols = st.columns(5)
    for i, card in enumerate(CARDS):
        score = pdf_data["match_scores"].get(card["id"], 0)
        is_recommended = card["id"] == recommended_id

        with cols[i]:
            rec_badge = "⭐ RECOMMENDED" if is_recommended else ""
            rec_cls = "recommended" if is_recommended else ""
            conf_cls = conf_class(score)

            st.markdown(
                f"""<div class="card-selector {rec_cls}" style="border-top: 3px solid {card['color']};">
                    <div style="font-size:36px;margin-bottom:8px;">{card['icon']}</div>
                    <div style="font-size:13px;font-weight:700;margin-bottom:4px;">{card['name']}</div>
                    <div style="font-size:11px;color:#888;margin-bottom:10px;min-height:40px;">{card['desc']}</div>
                    <div class="score-bar-bg">
                        <div class="score-bar-fill" style="width:{score}%;background:{card['color']};"></div>
                    </div>
                    <div class="conf-badge {conf_cls}" style="margin-top:6px;">{score}% match</div>
                    {'<div style="margin-top:8px;font-size:11px;color:#3b82f6;font-weight:600;">'+rec_badge+'</div>' if rec_badge else ''}
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                f"{'⭐ ' if is_recommended else ''}Select",
                key=f"card_{card['id']}",
                type="primary" if is_recommended else "secondary",
                use_container_width=True,
            ):
                select_card(card["id"])
                st.rerun()

    st.divider()

    # ── What happens if you pick the "wrong" card ──
    st.markdown("### ❓ What happens if I pick a different card?")
    st.markdown(
        """<div class="warn-box info">
        <strong>You can select ANY card type</strong> — even if it's not the recommended one.<br>
        The AI will try to fill all sections using extracted data. Sections that don't match will show
        "Not found in document" with a low confidence score. You can always switch back.
        </div>""",
        unsafe_allow_html=True,
    )

    with st.expander("Match scores for all cards"):
        for card in CARDS:
            score = pdf_data["match_scores"].get(card["id"], 0)
            is_rec = card["id"] == recommended_id
            label = f"{'⭐ ' if is_rec else ''}{card['icon']} {card['name']}"
            st.progress(score / 100, text=f"{label} — {score}%")


# ══════════════════════════════════════════
# PHASE 4: CARD VIEW
# ══════════════════════════════════════════
elif st.session_state.phase == "card_view":
    render_phase_bar()

    pdf_name = st.session_state.active_pdf
    pdf_data = st.session_state.uploaded_pdfs[pdf_name]
    card_id = st.session_state.selected_card
    card = next(c for c in CARDS if c["id"] == card_id)
    score = pdf_data["match_scores"].get(card_id, 0)

    recommended_id = None
    for c in CARDS:
        if c["pdf_type"] == pdf_data["detected_type"]:
            recommended_id = c["id"]
            break

    is_recommended = card_id == recommended_id

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {card['icon']} {card['name']}")
        st.caption(f"Source: {pdf_name}")
    with col2:
        st.markdown(
            f"""<div style="text-align:right;">
                <div class="conf-badge {conf_class(score)}" style="font-size:14px;padding:6px 14px;">
                    {score}% match
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    # Warnings based on match quality
    if score >= 80:
        st.markdown(
            f"""<div class="warn-box success">
            ✅ <strong>Excellent match!</strong> This card type is ideal for this document. All sections should be accurately filled.
            </div>""",
            unsafe_allow_html=True,
        )
    elif score >= 50:
        st.markdown(
            f"""<div class="warn-box warn">
            ⚠️ <strong>Partial match.</strong> Some sections may have incomplete data.
            The recommended card for this PDF is <strong>{next(c['name'] for c in CARDS if c['id']==recommended_id)}</strong>.
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<div class="warn-box error">
            ❌ <strong>Low match ({score}%).</strong> This card type doesn't align with your document.
            Most sections will show "Not found." Consider using
            <strong>{next(c['name'] for c in CARDS if c['id']==recommended_id)}</strong> instead.
            </div>""",
            unsafe_allow_html=True,
        )

    # Social value banner
    st.markdown(
        f"""<div style="padding:14px;background:rgba(168,85,247,0.06);border:1px solid rgba(168,85,247,0.15);
        border-radius:10px;font-size:13px;margin:10px 0 20px;">
        💡 {card['social']}
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Rendered card (HTML preview) ──
    tab1, tab2 = st.tabs(["📋 Card Preview", "🔧 Section Details"])

    with tab1:
        html = load_card_html(card["file"])
        if html and is_recommended:
            st.components.v1.html(html, height=900, scrolling=True)
        elif html and score >= 50:
            st.info(
                "Showing demo card. In production, sections would be filled from YOUR PDF's OCR data."
            )
            st.components.v1.html(html, height=900, scrolling=True)
        else:
            st.warning(
                "Low match — in production, most sections would show 'Not found in document.'"
            )
            st.markdown(
                "**Preview of card structure (sections would be mostly empty):**"
            )
            for section in card["sections"]:
                with st.expander(section, expanded=False):
                    st.markdown(
                        f"""<div style="padding:20px;background:#1a1b23;border-radius:8px;
                        text-align:center;color:#555;font-size:13px;">
                        ⚠️ Data not found in document for this section
                        </div>""",
                        unsafe_allow_html=True,
                    )

    with tab2:
        st.markdown("#### Card Sections")
        st.caption("Each section can be edited or regenerated independently")

        for j, section_name in enumerate(card["sections"]):
            # Simulate per-section confidence
            if is_recommended:
                sec_conf = random.randint(78, 98)
            elif score >= 50:
                sec_conf = random.randint(30, 70)
            else:
                sec_conf = random.randint(5, 25)

            sec_cls = conf_class(sec_conf)

            st.markdown(
                f"""<div class="section-card">
                    <div class="section-header-row">
                        <div class="section-title-text">{section_name}</div>
                        <div style="display:flex;gap:6px;">
                            <span class="tag-sm tag-edit">✏️ Editable</span>
                            <span class="tag-sm tag-regen">🔄 Regen</span>
                            <span class="tag-sm conf-badge {sec_cls}">{sec_conf}%</span>
                        </div>
                    </div>
                    <div style="font-size:12px;color:#888;">
                        {'✅ Filled from OCR data' if sec_conf >= 50 else '⚠️ Low confidence — may need manual input'}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Action buttons ──
    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🔀 Try Another Card", use_container_width=True):
            back_to_dashboard()
            st.rerun()
    with col2:
        st.button("🔄 Regenerate All", use_container_width=True)
    with col3:
        st.button("📥 Export PDF", use_container_width=True)
    with col4:
        st.button("📊 Export JSON", use_container_width=True)
    with col5:
        st.button("💾 Save Card", type="primary", use_container_width=True)
