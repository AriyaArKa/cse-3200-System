# 🖥️ Dashboard UI/UX Plan — DocuCard

> **Design Philosophy:** Think NotebookLM — upload sources, AI processes, user picks output format.

---

## 1. Core User Journey (3 Phases)

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  📤 UPLOAD  │───▶│  🤖 AI PROCESS   │───▶│  📋 CARD VIEW   │
│   Phase     │    │    Phase         │    │    Phase        │
└─────────────┘    └──────────────────┘    └─────────────────┘
```

### Phase 1: Upload (User Action)

- User uploads 1 or more PDFs (any type, any language)
- Drag-and-drop or file picker
- Shows file list with size, page count preview
- "Process All" button

### Phase 2: AI Processing (Automatic)

- **Step A:** PDF → Images (existing pdf.py)
- **Step B:** OCR via Gemini (existing ocr_image)
- **Step C:** Merge page JSONs (existing merge)
- **Step D:** **NEW** — Auto-classify PDF type (Gemini prompt)
- **Step E:** **NEW** — Extract structured data for card filling
- Progress bar per PDF, real-time status

### Phase 3: Dashboard & Card Selection (User Action)

- Shows all uploaded PDFs in a sidebar/list
- Each PDF shows: detected type + confidence badge
- **All 5 card types visible** — recommended one(s) glowing
- User clicks any card → system fills it with OCR data
- User edits, regenerates sections, exports

---

## 2. Screen-by-Screen Breakdown

### Screen 1: Landing / Upload

```
┌──────────────────────────────────────────────────┐
│  📄 DocuCard — AI Document Intelligence          │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │                                          │    │
│  │     📤 Drop your PDFs here               │    │
│  │     or click to upload                   │    │
│  │                                          │    │
│  │     Supports: Bangla, English, Mixed     │    │
│  │     Any PDF type — we auto-detect        │    │
│  │                                          │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Uploaded Files:                                 │
│  ┌──────────────────────────┐ ┌──────────────┐   │
│  │ 📄 notice.pdf  (2 pages) │ │ 📄 bank.pdf  │   │
│  │    120 KB                │ │   340 KB     │   │
│  │    [✕ Remove]            │ │   [✕ Remove] │   │
│  └──────────────────────────┘ └──────────────┘   │
│                                                  │
│          [ ▶ Process All PDFs ]                   │
└──────────────────────────────────────────────────┘
```

### Screen 2: Processing (Auto)

```
┌──────────────────────────────────────────────────┐
│  🔄 Processing 2 PDFs...                         │
│                                                  │
│  notice.pdf                                      │
│  ████████████████████░░░ 80%                     │
│  ✅ PDF→Images  ✅ OCR  🔄 Classifying...        │
│                                                  │
│  bank.pdf                                        │
│  ████████░░░░░░░░░░░░░░ 35%                     │
│  ✅ PDF→Images  🔄 OCR page 2/4...              │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Screen 3: Dashboard (Main View)

```
┌──────────────────────────────────────────────────────────────────┐
│  SIDEBAR                │  MAIN CONTENT                         │
│                         │                                       │
│  📄 Your Documents      │  📄 notice.pdf                        │
│  ─────────────────      │  Type: University Notice (94%)        │
│  📄 notice.pdf          │                                       │
│    🏷️ University Notice │  ┌─ Select Card Template ───────────┐ │
│    94% confidence       │  │                                   │ │
│    ✅ Processed          │  │  🎓 Student     💼 Job    🏛️ Gov  │ │
│                         │  │  Support ⭐     Eligib.   Policy  │ │
│  📄 bank.pdf            │  │  RECOMMENDED                      │ │
│    🏷️ Financial Doc     │  │                                   │ │
│    89% confidence       │  │  🏦 Financial   📋 Meeting        │ │
│    ✅ Processed          │  │  Health         Tracker           │ │
│                         │  │                                   │ │
│  ─────────────────      │  └───────────────────────────────────┘ │
│  [📤 Upload More]       │                                       │
│                         │  ⭐ = AI Recommended for this PDF     │
│                         │  You can select ANY card type          │
│                         │                                       │
└──────────────────────────────────────────────────────────────────┘
```

### Screen 4: Card View (After Selection)

```
┌──────────────────────────────────────────────────────────────────┐
│  SIDEBAR                │  CARD VIEW                            │
│                         │                                       │
│  📄 notice.pdf          │  🎓 Student Action & Support Card     │
│  Card: Student Support  │  ───────────────────────────────────  │
│                         │  Confidence: 94%  │ Source: notice.pdf│
│  Sections:              │                                       │
│  ✏️ What Is This About  │  ┌─ What Is This Notice About? ────┐ │
│  ✏️ Who Is Affected     │  │ ✨ AI Summary      [🔄 Regen]   │ │
│  ✏️ What You Must Do    │  │                                  │ │
│  ✏️ Important Deadlines │  │ ছুটি ঘোষণা — KUET কর্তৃপক্ষ...  │ │
│  ✏️ Risk If Ignored     │  │ [✏️ Edit]                        │ │
│                         │  └──────────────────────────────────┘ │
│  ─────────────────      │                                       │
│  [🔄 Try Another Card]  │  ┌─ Who Is Affected? ──────────────┐ │
│  [📥 Export]            │  │ • All students...                │ │
│  [📄 View Source PDF]   │  │ [✏️ Edit]                        │ │
│                         │  └──────────────────────────────────┘ │
│                         │                                       │
│                         │  [💾 Save]  [📥 Export]  [📄 PDF]    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. What Happens When User Uploads "Wrong" Card?

**Key Design Decision: Let the user choose ANY card type.**

| Scenario                            | System Behavior                                                                                           |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------- |
| University notice → Student Card ⭐ | Perfect match. AI fills all sections accurately. Confidence: ~90%+                                        |
| University notice → Job Card        | System tries to fit data. Many sections will say "Not found in document." Confidence: ~30%                |
| University notice → Financial Card  | Almost nothing matches. System shows warning: "This PDF doesn't contain financial data." Confidence: ~10% |
| Bank statement → Student Card       | Partial match possible (dates, amounts). AI warns: "This doesn't appear to be a university notice."       |
| User picks anyway                   | System fills what it can. Shows ⚠️ on low-confidence sections. User can edit everything.                  |

**Rules:**

1. AI always recommends the best card type (highlighted with ⭐)
2. User can override and select any card
3. Low-confidence selections show a warning banner
4. Each section shows individual confidence + source reference
5. User can switch card types without re-uploading

---

## 4. Multi-PDF Workflow

```
Upload 3 PDFs
    │
    ├── notice.pdf     → Auto: University Notice (94%)
    ├── salary.pdf     → Auto: Government Circular (87%)
    └── statement.pdf  → Auto: Financial Document (91%)

Dashboard shows all 3 in sidebar.
User clicks each one → sees recommended card → selects → views filled card.
Each PDF is independent. User can process them in any order.
```

---

## 5. NotebookLM-Style Features

| NotebookLM                  | DocuCard Equivalent                    |
| --------------------------- | -------------------------------------- |
| Upload sources (PDFs, URLs) | Upload PDFs (any type, Bangla/English) |
| AI reads and indexes        | Gemini OCR + auto-classify             |
| Generate summary            | Card with AI summary section           |
| Ask questions               | (Future) Chat about document           |
| Generate podcast            | (Future) Generate report               |
| Multiple output formats     | 5 card types — user picks              |
| Edit and refine             | Edit any section, regenerate AI parts  |
| Source citations            | Each section links to source page/text |

---

## 6. Card Selection Logic (Backend)

```python
# Pseudocode for classification + card recommendation

def classify_and_recommend(ocr_text: str) -> dict:
    """
    1. Send OCR text to Gemini with classification prompt
    2. Get PDF type + confidence
    3. Map PDF type → recommended card template
    4. Return all 5 cards with match scores
    """

    TYPE_TO_CARD = {
        "University Notice":           "student_support_card",
        "Government Circular":         "government_policy_impact_card",
        "Job & Recruitment Document":  "job_eligibility_checker_card",
        "Financial & Banking Document": "financial_health_card",
        "Meeting & Administrative":    "meeting_decision_tracker_card",
    }

    # Gemini classifies
    result = gemini_classify(ocr_text)
    # Returns: { type: "University Notice", confidence: 0.94 }

    recommended = TYPE_TO_CARD[result["type"]]

    return {
        "detected_type": result["type"],
        "confidence": result["confidence"],
        "recommended_card": recommended,
        "all_cards": [
            {"id": "student_support_card",          "match": 0.94, "recommended": True},
            {"id": "job_eligibility_checker_card",   "match": 0.15, "recommended": False},
            {"id": "government_policy_impact_card",  "match": 0.20, "recommended": False},
            {"id": "financial_health_card",          "match": 0.05, "recommended": False},
            {"id": "meeting_decision_tracker_card",  "match": 0.10, "recommended": False},
        ]
    }
```

---

## 7. Export Options

| Format      | Description                            |
| ----------- | -------------------------------------- |
| 📄 PDF      | Beautiful PDF version of the card      |
| 📊 JSON     | Structured JSON (for API/integration)  |
| 📋 Markdown | For sharing in docs/chats              |
| 🖼️ Image    | Screenshot-style PNG of the card       |
| 📥 HTML     | Standalone HTML file (like demo cards) |

---

## 8. Future Enhancements (Post-MVP)

1. **Batch Processing** — Upload 50 PDFs, auto-generate all cards
2. **Chat with Document** — Ask questions about the PDF (like NotebookLM)
3. **Card Comparison** — Compare two PDFs side by side
4. **History** — View previously processed PDFs and cards
5. **Templates Marketplace** — Users create and share custom card types
6. **API Access** — REST API for programmatic card generation
7. **Collaboration** — Share cards with team members
8. **Notifications** — Alert when deadlines (from cards) are approaching
