# BanglaDOC — Final Master Prompt for Cursor
## One file. Read completely before writing any code.

---

## HOW TO USE THIS PROMPT IN CURSOR

**Model selection — follow this strictly:**

- **Phase 1 (OCR fixes, Days 1–2):** Use `claude-sonnet-4-5` — surgical code edits, fast iteration
- **Phase 2 (Backend foundation, Days 3–5):** Use `claude-sonnet-4-5` — boilerplate generation
- **Phase 3 (RAG + Chatbot, Days 6–8):** Use `claude-opus-4-5` — complex reasoning, multilingual logic
- **Phase 4 (Frontend, Days 9–12):** Use `claude-sonnet-4-5` — component generation
- **Phase 5 (Research + Polish, Days 13–14):** Use `claude-opus-4-5` — synthesis, documentation

**How to give this to Cursor:**
1. Save this file as `CURSOR_PROMPT.md` in your project root
2. Open Cursor, press `Cmd+Shift+P` → "Add file to context" → select `CURSOR_PROMPT.md`
3. For each phase, tell Cursor: *"Follow CURSOR_PROMPT.md Phase N, Step X only. Stop after that step and wait."*
4. Never ask Cursor to do multiple phases at once — it will lose context
5. After each step, verify the output matches the expected result described below each step

---

## STOP BEFORE STARTING — VERIFY YOUR ENVIRONMENT

Run these commands first. Do not proceed until all pass:

```bash
# Python version
python3 --version        # must be 3.14.x

# Ollama — most critical for Bangla quality
ollama list              # must show qwen2.5vl:7b
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# If qwen2.5vl:7b not listed:
ollama pull qwen2.5vl:7b
ollama serve             # run in separate terminal, keep running

# PostgreSQL
docker compose up -d postgres
psql -h localhost -U bangladoc -d bangladoc -c "SELECT 1"

# Node
node --version           # must be 18+
npm --version
```

**If Ollama is not running with qwen2.5vl:7b, your Bangla OCR quality will be ~70% instead of ~85%. Fix this before anything else.**

---

## PROJECT IDENTITY

**Name:** BanglaDOC  
**Purpose:** Hybrid OCR + RAG system for Bengali and English government PDF documents. Extracts text from scanned PDFs with high accuracy, stores in a searchable corpus, and provides a multilingual AI chatbot for document question-answering.

**What makes it unique for research:**
1. First system combining confidence-tier-aware Bangla OCR with cross-lingual dense RAG for Bengali+English government documents
2. Quantified ablation study: EasyOCR-only (70%) vs Ollama-primary (85%) on real government PDFs
3. Bangla-aware chunking that preserves conjunct character boundaries across chunk splits
4. Bijoy/SutonnyMJ legacy font detection that prevents 478-second processing loops
5. Per-page engine attribution (which engine processed each page) enabling granular quality tracking

**Real use cases:**
- University scholarship notice retrieval (KUET documents)
- Government gazette lookup by ministry, date, Smarak number
- Cross-document policy QA in Bengali
- Corporate loan document analysis
- OCR quality vs RAG retrieval accuracy correlation study

---

## CURRENT STATE (What Exists)

Your working directory contains `last_try_OCR/` package with:

```
last_try_OCR/
├── assets/bangla_wordlist.txt    ✓ keep
├── core/
│   ├── ocr_engine.py             ✓ keep → fix English-only mode
│   └── pdf_router.py             ✓ keep as-is
├── fallback/
│   └── llm_fallback.py           ✓ keep → split Ollama/Gemini logic
├── nlp/
│   ├── bangla_corrector.py       ✓ keep → ADD Stage F
│   ├── confidence_scorer.py      ✓ keep as-is
│   ├── numeric_validator.py      ✓ keep → ADD smarak normalizer
│   └── unicode_validator.py      ✓ keep → ADD Bijoy detector at top
├── output/json_builder.py        ✓ keep as-is
├── extraction/
│   ├── image_processor.py        ✓ keep (PDF pages only)
│   └── table_handler.py          ✓ keep as-is
├── server/app.py                 → SPLIT into FastAPI app structure
├── static/index.html             → DELETE (replace with React)
├── pipeline.py                   ✓ keep → fix Ollama silence bug
├── config.py                     ✓ keep → migrate to Pydantic Settings
├── exceptions.py                 ✓ keep as-is
├── models.py                     ✓ keep as-is
├── ocr_prompt.txt                → MOVE to prompts/ocr_bangla.txt
└── ollama_prompt.txt             → MOVE to prompts/ocr_ollama.txt
```

**Three confirmed bugs from real output analysis:**
- Bug 1: Ollama silently fails → EasyOCR runs instead → output says "EasyOCR" with no warning
- Bug 2: Bijoy font PDFs take 478+ seconds because `validate_digital_text()` misses them
- Bug 3: EasyOCR outputs `|` instead of `।`, `১০২৬` instead of `২০২৬`, noise chars like `` ` ^ ``

---

## TARGET STRUCTURE (Final)

```
bangladoc/                              ← rename project root
│
├── backend/
│   ├── bangladoc_ocr/                  ← renamed from last_try_OCR
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── models.py
│   │   ├── pipeline.py                 ← FIXED
│   │   ├── assets/
│   │   │   └── bangla_wordlist.txt
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── engine_easyocr.py       ← renamed, English-only
│   │   │   ├── engine_ollama.py        ← extracted from llm_fallback
│   │   │   ├── engine_gemini.py        ← extracted from llm_fallback
│   │   │   ├── pdf_router.py
│   │   │   └── preprocessor.py         ← NEW: quick_bangla_estimate
│   │   ├── nlp/
│   │   │   ├── __init__.py
│   │   │   ├── bangla_corrector.py     ← + Stage F
│   │   │   ├── confidence_scorer.py
│   │   │   ├── numeric_validator.py    ← + smarak normalizer
│   │   │   └── unicode_validator.py    ← + Bijoy detector
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── image_processor.py
│   │   │   └── table_handler.py
│   │   └── output/
│   │       ├── __init__.py
│   │       └── json_builder.py
│   │
│   ├── app/                            ← NEW FastAPI layer
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── schemas.py
│   │   ├── documents/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── schemas.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── embedder.py
│   │   │   ├── chunker.py
│   │   │   └── schemas.py
│   │   ├── chat/                       ← NEW: multilingual chatbot
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   └── schemas.py
│   │   ├── admin/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   ├── monitoring/
│   │   │   ├── __init__.py
│   │   │   └── router.py
│   │   └── websocket/
│   │       ├── __init__.py
│   │       └── manager.py
│   │
│   ├── prompts/
│   │   ├── ocr_bangla.txt
│   │   ├── ocr_ollama.txt
│   │   ├── rag_qa_bangla.txt           ← NEW
│   │   └── chat_system.txt             ← NEW
│   │
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_ocr_pipeline.py
│   │   ├── test_rag.py
│   │   └── test_chat.py
│   ├── scripts/
│   │   ├── seed_db.py
│   │   └── benchmark.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── documents.ts
│   │   │   ├── rag.ts
│   │   │   ├── chat.ts
│   │   │   └── monitoring.ts
│   │   ├── store/
│   │   │   ├── auth.store.ts
│   │   │   └── document.store.ts
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Upload.tsx
│   │   │   ├── DocumentViewer.tsx
│   │   │   ├── Chat.tsx               ← RAG chatbot page
│   │   │   └── Admin.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── PageTabs.tsx
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   ├── status/
│   │   │   │   ├── EngineStatusBar.tsx
│   │   │   │   └── ConfidenceRing.tsx
│   │   │   ├── document/
│   │   │   │   ├── DocumentTable.tsx
│   │   │   │   ├── PageViewer.tsx
│   │   │   │   ├── TextAnnotated.tsx
│   │   │   │   └── ExportButtons.tsx
│   │   │   ├── upload/
│   │   │   │   ├── DropZone.tsx
│   │   │   │   └── ProcessingCard.tsx
│   │   │   └── chat/
│   │   │       ├── ChatWindow.tsx
│   │   │       ├── MessageBubble.tsx
│   │   │       ├── SourceCitation.tsx
│   │   │       └── CollectionPicker.tsx
│   │   ├── hooks/
│   │   │   ├── useOCRProgress.ts
│   │   │   ├── useEngineStatus.ts
│   │   │   └── useChat.ts
│   │   └── styles/
│   │       └── globals.css
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── data/                               ← gitignored
│   ├── uploads/
│   ├── output_images/
│   ├── output_jsons/
│   ├── merged_outputs/
│   ├── corpus/
│   └── chroma/
│
├── docker-compose.yml
├── Makefile
├── .gitignore
└── README.md
```

---

# PHASE 1 — OCR FIXES
# Model: claude-sonnet-4-5 | Days 1–2

**Tell Cursor:** *"Read CURSOR_PROMPT.md Phase 1. Implement Step 1.1 only. Show me the diff and stop."*

---

## Step 1.1 — Fix `unicode_validator.py`: Bijoy Font Detector

**Why this first:** The Bangla Academy PDF took 478 seconds because this check is missing. 10 seconds to add, saves minutes per bad PDF.

**Expected result:** After this fix, re-run `d972f997a3d547bf95962a80f69ed055-3.pdf` — processing time drops from 478s to ~30s.

Open `last_try_OCR/nlp/unicode_validator.py`. Add these before the `validate_digital_text` function:

```python
# ── Bijoy/SutonnyMJ early detection (prevents 478s processing loops) ──────
_BRACKET_NOISE_RE = re.compile(r'\d+\[\d+\]\d+')
_MIXED_WORD_RE    = re.compile(r'[\u0980-\u09FF]+[a-zA-Z]+[\u0980-\u09FF]*')
_GARBLED_EMAIL_RE = re.compile(r'[\u0980-\u09FF]+@|@[\u0980-\u09FF]')


def _detect_bijoy_font(text: str) -> bool:
    """
    Detect Bijoy/SutonnyMJ legacy Bengali font in PyMuPDF-extracted text.
    These PDFs look digital (many chars) but are Bijoy-encoded garbage.

    Tested against: Bangla Academy PDF (d972f997...) — 81[64]47 pattern,
    garbled email 'paruaacademirogmail.con', mixed word 'বাংনা' etc.
    Returns True → caller must reroute page to OCR engine.
    """
    if len(text) < 200:
        return False

    score = 0
    if len(_MIXED_WORD_RE.findall(text)) >= 3:       score += 2  # 'বাংনা', 'সেশলাচ'
    if _GARBLED_EMAIL_RE.search(text):                score += 2  # email with Bengali
    if len(_BRACKET_NOISE_RE.findall(text)) >= 1:     score += 2  # '81[64]47'
    if bangla_char_ratio(text) < 0.15 and len(text) > 500: score += 1
    if winansa_artifact_count(text) >= 2:             score += 1

    return score >= 3
```

Then add this at the very TOP of `validate_digital_text()`, before any existing logic:

```python
def validate_digital_text(text: str) -> Tuple[bool, dict]:
    report: dict = {}

    # FAST EXIT: Bijoy/SutonnyMJ font — prevents 478-second processing loops.
    # Must be first check. If triggered, skip ALL other validation.
    if _detect_bijoy_font(text):
        report["bijoy_detected"] = True
        report["is_valid"] = False
        report["rejection_reasons"] = [
            "Bijoy/SutonnyMJ legacy font detected — rerouting page to OCR engine"
        ]
        logger.warning(
            "Bijoy font early exit: text len=%d — rerouting to OCR", len(text)
        )
        return False, report

    # ... rest of existing function unchanged from here ...
```

**Verify:** `python3 -c "from last_try_OCR.nlp.unicode_validator import validate_digital_text; print(validate_digital_text('বাংনা ওয়েব সাহঢ 81[64]47 paruaacademirogmail.con bacadem1955@yahoo ' * 10))"` — should return `is_valid: False, bijoy_detected: True`

---

## Step 1.2 — Fix `bangla_corrector.py`: Stage F Artifact Cleanup

**Why:** Every single Bangla scanned output has `|` instead of `।`, backtick noise, and year digit errors. This is a regex fix — no ML needed, adds ~3% to confidence score.

Add after existing imports in `last_try_OCR/nlp/bangla_corrector.py`:

```python
# ── Stage F: EasyOCR artifact cleanup (confirmed from real output analysis) ─
_PIPE_TO_DANDA  = re.compile(r'\|(?=\s|$|\n)')
_BRACKET_DANDA  = re.compile(r'(?<=[।\s\u0980-\u09FF])[\[\]](?=\s|$|\n)')
_BACKTICK_NOISE = re.compile(r'[`^~]{1,3}')
# Bengali year: ১০XX → ২০XX (digit ১ misread as ২ in year context)
_YEAR_FIX       = re.compile(r'(?<!\d)১০([২-৯]\d)(?!\d)')
# ASCII digits inside Bengali Smarak numbers → Bengali
_ASCII_TO_BN    = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
_SMARAK_RE      = re.compile(r'(স্মারক\s*নং\s*[:।]?\s*)([\d০-৯.\s/]+)')

# Confirmed word-level confusions from real output files
# (notice_durga_puja, gazette, forwarding — all 7 Bangla scanned docs)
_EASYOCR_WORD_FIXES: dict[str, str] = {
    'বুলনা':       'খুলনা',      # ব/খ visual confusion (notice_durga_puja)
    'নিজ্ঞপ্তি': 'বিজ্ঞপ্তি',  # ন/ব confusion
    'নিজ্ঞপতি':  'বিজ্ঞপ্তি',
    'অব্র':        'অত্র',        # ব/ত confusion (notice_durga_puja)
    'প্রজ্ঞীপন':  'প্রজ্ঞাপন',  # gazette vowel error
    'প্রজ্ঞাপণ':  'প্রজ্ঞাপন',
    'মাচ ':        'মার্চ ',      # month (gazette)
    'মার্ছ ':      'মার্চ ',
    'বন্ খাকবে':  'বন্ধ থাকবে', # dropped hasanta (notice_durga_puja)
    'বন্ থাকবে':  'বন্ধ থাকবে',
}


def fix_easyocr_artifacts(text: str) -> Tuple[str, bool]:
    """
    Stage F: Clean known EasyOCR artifact patterns.
    ONLY call when source == 'easyocr' or 'easyocr_fallback'.
    Confirmed against: notice_durga(0.66), gazette(0.72), forwarding(0.79),
    Image_001(0.74), Freedom_Fight(0.74) — all 7 Bangla scanned documents.
    """
    original = text

    text = _PIPE_TO_DANDA.sub('।', text)
    text = _BRACKET_DANDA.sub('।', text)
    text = _BACKTICK_NOISE.sub('', text)
    text = _YEAR_FIX.sub(lambda m: '২০' + m.group(1), text)

    # Smarak number: convert any ASCII digits to Bengali
    def _fix_smarak(m: re.Match) -> str:
        return m.group(1) + m.group(2).translate(_ASCII_TO_BN)
    text = _SMARAK_RE.sub(_fix_smarak, text)

    for wrong, right in _EASYOCR_WORD_FIXES.items():
        text = text.replace(wrong, right)

    return text, (text != original)
```

Then add Stage F call at the end of `correct_bangla_text()` before the final return:

```python
    # Stage F: EasyOCR artifact cleanup
    if source in ('easyocr', 'easyocr_fallback', 'EasyOCR_fallback'):
        text, was_fixed = fix_easyocr_artifacts(text)
        if was_fixed:
            log['corrections'].append('stage_f_easyocr_artifacts')
            log['stage_f_fixes'] = sum(
                1 for w in _EASYOCR_WORD_FIXES if w in original
            )

    log['corrected_length'] = len(text)
    log['edit_distance'] = _simple_edit_distance_ratio(original, text)
    return text, log
```

**Verify:** `assert 'বিজ্ঞপ্তি' in fix_easyocr_artifacts('নিজ্ঞপ্তি')[0]` — should pass

---

## Step 1.3 — Fix `pipeline.py`: Ollama Failure Transparency

**Why this is critical:** Every single Bangla document shows `"trying_ollama_first"` in decisions but `engine: "EasyOCR"` in the result. You have been benchmarking EasyOCR the whole time, not Ollama. This fix exposes what is actually happening.

Find where Ollama is called in `pipeline.py`. Replace the silent try/except with:

```python
# Add at module level:
_ollama_failed_this_session: bool = False


def _try_ollama_page(
    img_bytes: bytes,
    page_num: int,
    decisions: list,
) -> Optional[any]:
    """
    Attempt Ollama with full failure transparency.
    Returns result on success, None on any failure.
    Caller MUST check return value and log engine name accordingly.
    """
    global _ollama_failed_this_session

    if not config.OLLAMA_ENABLED or _ollama_failed_this_session:
        decisions.append({
            'page': page_num,
            'keyword': 'OLLAMA_SKIPPED',
            'detail': 'disabled or previous failure this session',
            'severity': 'info',
        })
        return None

    import time
    t0 = time.time()
    try:
        # replace with your actual Ollama call
        result = _call_ollama(img_bytes)
        elapsed = time.time() - t0
        model = config.get_status().get('ollama_model', 'unknown')
        decisions.append({
            'page': page_num,
            'keyword': 'OLLAMA_SUCCESS',
            'detail': f'model={model} elapsed={elapsed:.1f}s conf={getattr(result, "confidence", 0):.3f}',
            'severity': 'info',
        })
        return result

    except Exception as exc:
        elapsed = time.time() - t0
        logger.warning(
            'Ollama FAILED page %d after %.1fs — %s: %s',
            page_num, elapsed, type(exc).__name__, str(exc)[:120],
        )
        decisions.append({
            'page': page_num,
            'keyword': 'OLLAMA_FAILED',
            'detail': f'{type(exc).__name__}: {str(exc)[:100]}',
            'severity': 'warning',
        })
        config.set_status('ollama_available', False)
        _ollama_failed_this_session = True
        return None


# When calling, always set engine name explicitly:
# ollama_result = _try_ollama_page(img_bytes, page_num, decisions)
# if ollama_result:
#     extraction.engine = f"ollama:{config.get_status()['ollama_model']}"
# else:
#     extraction.engine = "easyocr_fallback"   ← NOT "easyocr"
```

**Verify:** After this fix, re-run `notice_durga_puja.pdf`. The output JSON decisions should now show either `OLLAMA_SUCCESS` or `OLLAMA_FAILED` — never the ambiguous `"trying_ollama_first"` without outcome.

---

## Step 1.4 — Update OCR Prompts

**Replace content of `prompts/ocr_ollama.txt`** (keep existing content, prepend this block):

```
=== CRITICAL RULES — READ FIRST, APPLY TO EVERY PAGE ===

PUNCTUATION:
- Bangla sentence end: use । (U+0964 — danda). NEVER use | (pipe) or [ or ].
- One sentence = ends with ।   Multiple sentences = each ends with ।
- কমা (,) for lists.   দাড়ি (।) for sentence end.   Nothing else.

YEAR DIGITS:
- Bengali years 2020–2029 start with ২০. Never ১০XX.
- ২০২৬ = year 2026.   If you write ১০২৬ you are wrong.
- Bengali ২ has a curved belly. Bengali ১ is a simple stroke.

SMARAK NUMBER (স্মারক নং):
- Contains ONLY Bengali digits ০-৯. Never mix ASCII (0-9) with Bengali.
- Correct: ৩৭.৭২.৪৭০০ ০০০ ০০১ ৯৯০০৫৩ ২৬ ৫৩
- Wrong:   37.72.4700 000 001 990053 26 53
- If source image shows mixed digits → convert ALL to Bengali.

SPECIFIC WORDS (common in KUET/Khulna/government documents):
- খুলনা (city) starts with খ. Never write বুলনা.
- বিজ্ঞপ্তি (notice) starts with ব, conjunct জ্ঞ. Full: বিজ্ঞপ্তি
- অত্র (herein) has ত as second letter. Never অব্র.
- প্রজ্ঞাপন (gazette) vowel is আ-কার (া). Never প্রজ্ঞীপন.
- বন্ধ (closed) has hasanta joining ন+ধ. Never বন্ with trailing space.
- শিক্ষার্থী (student) full conjunct ক্ষ. Never শিহদার্ণী.

SEALS AND NOISE:
- Scattered syllables near a circular stamp area → write [SEAL: description]
- Isolated 2-3 characters with no word meaning → skip them
- Never output noise fragments like 'সৎঙ্' or '৩ম|৩]'

EMAIL AND WEB:
- Email addresses are Latin only. Never mix Bengali into email text.
- Web URLs are Latin only. banglaacademy.gov.bd not বাংলাacademy.gov.bd

=== ORIGINAL PROMPT CONTINUES BELOW ===
```

---

## Step 1.5 — Benchmark Before/After

Run this benchmark script to confirm fixes work. Save as `scripts/benchmark_phase1.py`:

```python
"""
Phase 1 benchmark — run all available test PDFs, compare confidence before/after fixes.
Usage: python scripts/benchmark_phase1.py path/to/test_pdfs/
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from last_try_OCR.pipeline import process_pdf

EXPECTED_IMPROVEMENTS = {
    'notice_durga_puja': {'conf_before': 0.6633, 'time_before': 236.1, 'conf_target': 0.70},
    'bangla_academy':    {'conf_before': 0.6968, 'time_before': 478.5, 'time_target': 40.0},
    'gazette':           {'conf_before': 0.7238, 'time_before': 148.1, 'conf_target': 0.74},
}

if __name__ == '__main__':
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('test_pdfs')
    results = []

    for pdf in sorted(pdf_dir.glob('*.pdf')):
        t0 = time.time()
        result = process_pdf(str(pdf), use_multiprocessing=False)
        elapsed = time.time() - t0
        summary = result.to_dict()['document']['processing_summary']

        row = {
            'name': pdf.stem,
            'pages': result.total_pages,
            'conf': round(summary['overall_confidence'], 4),
            'time_s': round(elapsed, 1),
            'ollama_pages': summary.get('pages_sent_to_api', 0),
            'easyocr_fallback': summary.get('pages_processed_locally', 0),
        }
        results.append(row)
        status = '✓' if row['conf'] > EXPECTED_IMPROVEMENTS.get(pdf.stem, {}).get('conf_before', 0) else '✗'
        print(f"{status} {pdf.stem}: conf={row['conf']} time={row['time_s']}s")

    # Save for research paper
    with open('data/benchmark_phase1.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\nSaved to data/benchmark_phase1.json')
```

**Phase 1 complete when:** All 8 test PDFs run without errors, Bijoy PDF processes in < 40s, `stage_f_easyocr_artifacts` appears in correction logs.

---

# PHASE 2 — BACKEND FOUNDATION
# Model: claude-sonnet-4-5 | Days 3–5

**Tell Cursor:** *"Read CURSOR_PROMPT.md Phase 2. Implement steps in order. Stop after each step and show the result."*

---

## Step 2.1 — Project Structure + Dependencies

Create `docker-compose.yml`:
```yaml
version: '3.9'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: bangladoc
      POSTGRES_PASSWORD: bangladoc
      POSTGRES_DB: bangladoc
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bangladoc"]
      interval: 5s
      retries: 5
volumes:
  pgdata:
```

Create `backend/pyproject.toml`:
```toml
[project]
name = "bangladoc-backend"
version = "1.0.0"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.3",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "python-multipart>=0.0.9",
    "slowapi>=0.1.9",
    "httpx>=0.27",
    "chromadb>=0.5",
    "sentence-transformers>=3.0",
    "easyocr>=1.7",
    "pymupdf>=1.24",
    "pdfplumber>=0.11",
    "opencv-python-headless>=4.10",
    "Pillow>=10.0",
    "aiofiles>=23.0",
    "python-dotenv>=1.0",
    "pandas>=2.0",
    "pyarrow>=16.0",
    "numpy>=1.26",
    "google-genai>=0.8",
]
```

Create `backend/.env`:
```env
DATABASE_URL=postgresql+asyncpg://bangladoc:bangladoc@localhost:5432/bangladoc
SECRET_KEY=CHANGE_THIS_generate_with_python_secrets_token_hex_32
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=
GEMINI_ENABLED=false
USE_GPU=false
MAX_WORKERS=2
LOG_LEVEL=INFO
UPLOAD_DIR=../data/uploads
CHROMA_DIR=../data/chroma
```

Run:
```bash
docker compose up -d postgres
cd backend && pip install -e .
```

---

## Step 2.2 — Pydantic Settings (`backend/app/config.py`)

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bangladoc:bangladoc@localhost:5432/bangladoc"

    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Storage
    BASE_DIR: Path = Path(__file__).parent.parent
    UPLOAD_DIR: Path = BASE_DIR / ".." / "data" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / ".." / "data"
    CHROMA_DIR: Path = BASE_DIR / ".." / "data" / "chroma"

    # OCR
    USE_GPU: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_PRIORITY: list[str] = [
        "qwen2.5vl:7b", "minicpm-v:8b", "llava:13b", "llava:7b"
    ]
    OLLAMA_TIMEOUT: int = 180
    GEMINI_API_KEY: str = ""
    GEMINI_ENABLED: bool = False

    # Bangla OCR thresholds
    BANGLA_DIRECT_LLM_THRESHOLD: float = 0.40
    API_FALLBACK_THRESHOLD_BANGLA: float = 0.62
    API_FALLBACK_THRESHOLD_ENGLISH: float = 0.55
    LLM_BANGLA_CONFIDENCE_FLOOR: float = 0.86

    # Performance (M4 16GB)
    MAX_WORKERS: int = 2
    PAGE_BATCH_SIZE: int = 10
    MAX_PDF_SIZE_MB: int = 100

    # RAG
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    RAG_CHUNK_SIZE: int = 400
    RAG_CHUNK_OVERLAP: int = 80
    RAG_TOP_K: int = 5

    # Chat
    CHAT_TEXT_MODEL: str = "qwen2.5:7b"  # text-only, not vision
    CHAT_MAX_HISTORY: int = 20            # messages per session

    # Limits
    UPLOAD_RATE_LIMIT: str = "20/hour"
    CHAT_RATE_LIMIT: str = "60/minute"
    DEFAULT_STORAGE_QUOTA_MB: int = 500


settings = Settings()
```

---

## Step 2.3 — Database + Models

`backend/app/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

`backend/app/auth/models.py` — implement User + RefreshToken with these exact columns:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id:               Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email:            Mapped[str]       = mapped_column(String(255), unique=True, index=True)
    username:         Mapped[str]       = mapped_column(String(100), unique=True, index=True)
    hashed_password:  Mapped[str]       = mapped_column(String(255))
    role:             Mapped[str]       = mapped_column(String(20), default="user")
    is_active:        Mapped[bool]      = mapped_column(Boolean, default=True)
    storage_quota_mb: Mapped[int]       = mapped_column(Integer, default=500)
    created_at:       Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)
    documents:     Mapped[list["Document"]]     = relationship(back_populates="owner")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id:         Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id:    Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str]       = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime]  = mapped_column(DateTime)
    revoked:    Mapped[bool]      = mapped_column(Boolean, default=False)
    user:       Mapped["User"]    = relationship(back_populates="refresh_tokens")
```

`backend/app/documents/models.py`:
```python
class Document(Base):
    __tablename__ = "documents"
    id:                     Mapped[uuid.UUID]         = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id:               Mapped[uuid.UUID]         = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename:               Mapped[str]               = mapped_column(String(500))
    original_filename:      Mapped[str]               = mapped_column(String(500))
    file_size_bytes:        Mapped[int]
    total_pages:            Mapped[int]               = mapped_column(default=0)
    language_detected:      Mapped[str]               = mapped_column(String(50), default="unknown")
    overall_confidence:     Mapped[float]             = mapped_column(default=0.0)
    status:                 Mapped[str]               = mapped_column(String(30), default="pending")
    domain:                 Mapped[str]               = mapped_column(String(100), default="general")
    is_indexed_rag:         Mapped[bool]              = mapped_column(Boolean, default=False)
    chroma_collection_id:   Mapped[Optional[str]]     = mapped_column(String(200), nullable=True)
    processing_time_ms:     Mapped[float]             = mapped_column(default=0.0)
    ollama_pages:           Mapped[int]               = mapped_column(Integer, default=0)
    easyocr_fallback_pages: Mapped[int]               = mapped_column(Integer, default=0)
    bijoy_font_detected:    Mapped[bool]              = mapped_column(Boolean, default=False)
    error_message:          Mapped[Optional[str]]     = mapped_column(Text, nullable=True)
    created_at:             Mapped[datetime]          = mapped_column(DateTime, default=datetime.utcnow)
    completed_at:           Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    owner:   Mapped["User"]          = relationship(back_populates="documents")
    pages:   Mapped[list["PageRecord"]] = relationship(back_populates="document", cascade="all, delete")


class PageRecord(Base):
    __tablename__ = "pages"
    id:                   Mapped[uuid.UUID]       = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id:          Mapped[uuid.UUID]       = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page_number:          Mapped[int]
    full_text:            Mapped[str]             = mapped_column(Text, default="")
    engine_used:          Mapped[str]             = mapped_column(String(60))
    # engine_used values: "ollama:qwen2.5vl:7b" | "easyocr_fallback" | "PyMuPDF"
    confidence_score:     Mapped[float]
    confidence_tier:      Mapped[str]             = mapped_column(String(10))
    language_ratio_bn:    Mapped[float]           = mapped_column(default=0.0)
    has_table:            Mapped[bool]            = mapped_column(Boolean, default=False)
    word_count:           Mapped[int]             = mapped_column(Integer, default=0)
    source_image_path:    Mapped[str]             = mapped_column(String(500), default="")
    verified:             Mapped[bool]            = mapped_column(Boolean, default=False)
    processing_time_ms:   Mapped[float]           = mapped_column(default=0.0)
    artifact_corrections: Mapped[int]             = mapped_column(Integer, default=0)
    ollama_attempted:     Mapped[bool]            = mapped_column(Boolean, default=False)
    ollama_succeeded:     Mapped[bool]            = mapped_column(Boolean, default=False)
    document:             Mapped["Document"]      = relationship(back_populates="pages")
```

Run migrations:
```bash
cd backend && alembic init alembic
# Configure alembic/env.py for async — see Step 2.4
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

---

## Step 2.4 — Auth Module

`backend/app/auth/service.py` — implement these functions completely:

```python
import hashlib, secrets, uuid
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, role: str) -> str:
    return jwt.encode(
        {"sub": user_id, "role": role, "type": "access",
         "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)},
        settings.SECRET_KEY, algorithm="HS256",
    )


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store ONLY the hash in DB."""
    raw = secrets.token_urlsafe(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_access_token(token: str) -> dict:
    """Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


async def register_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    # Check uniqueness, hash password, insert, commit
    ...


async def login(db: AsyncSession, email: str, password: str) -> dict:
    # Verify credentials, create both tokens, store refresh hash
    # Return {"access_token": ..., "refresh_token": ..., "token_type": "bearer"}
    ...


async def refresh_tokens(db: AsyncSession, raw_refresh: str) -> dict:
    # Verify refresh token hash, check not revoked, check not expired
    # Revoke old token, create new pair (rotation)
    ...
```

Auth routes (`backend/app/auth/router.py`):
```
POST /api/auth/register  → RegisterRequest → TokenResponse
POST /api/auth/login     → LoginRequest → TokenResponse
POST /api/auth/refresh   → RefreshRequest → TokenResponse
POST /api/auth/logout    → revoke refresh token → 204
GET  /api/auth/me        → current user info
```

---

## Step 2.5 — Document Service (Pipeline Bridge)

`backend/app/documents/service.py` — this is the most critical service. It bridges OCR pipeline to DB with real-time WebSocket progress:

```python
import asyncio
import uuid
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from bangladoc_ocr.pipeline import process_pdf
from app.websocket.manager import ws_manager


async def process_document_async(
    document_id: uuid.UUID,
    pdf_path: Path,
    user_id: uuid.UUID,
    domain: str,
    db: AsyncSession,
) -> None:
    """
    Background task: runs OCR, stores results, broadcasts progress.
    Called via BackgroundTasks — NOT awaited by the upload endpoint.
    """
    loop = asyncio.get_event_loop()

    def progress_cb(current_page: int, total_pages: int) -> None:
        """Sync callback from OCR thread → sends WS message."""
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast_to_user(str(user_id), {
                "type": "ocr_progress",
                "document_id": str(document_id),
                "current_page": current_page,
                "total_pages": total_pages,
                "percent": round(current_page / max(total_pages, 1) * 100, 1),
            }),
            loop,
        ).result(timeout=2)

    await _update_document_status(db, document_id, "processing")

    try:
        # Run blocking OCR in thread pool
        result = await asyncio.to_thread(
            process_pdf,
            str(pdf_path),
            False,       # no multiprocessing (already in thread)
            domain,
            progress_cb,
        )

        # Persist all pages to DB
        pages_to_insert = []
        for page in result.pages:
            rec = page.to_corpus_record()
            ext = page.extraction
            pages_to_insert.append(PageRecord(
                document_id=document_id,
                page_number=rec["page_number"],
                full_text=rec["full_text"],
                engine_used=ext.engine,
                confidence_score=rec["confidence_score"],
                confidence_tier=rec["confidence_tier"],
                language_ratio_bn=rec["language_ratio_bn"],
                has_table=rec["has_table"],
                word_count=rec["word_count"],
                source_image_path=rec["source_image_path"],
                artifact_corrections=page.log.get("stage_f_fixes", 0),
                ollama_attempted="OLLAMA" in " ".join(
                    d.get("keyword", "") for d in page.decisions
                ),
                ollama_succeeded=any(
                    d.get("keyword") == "OLLAMA_SUCCESS" for d in page.decisions
                ),
            ))

        db.add_all(pages_to_insert)

        # Update document summary
        summary = result.to_dict()["document"]["processing_summary"]
        doc = await db.get(Document, document_id)
        doc.status = "completed"
        doc.total_pages = result.total_pages
        doc.overall_confidence = summary["overall_confidence"]
        doc.processing_time_ms = summary["processing_time_ms"]
        doc.ollama_pages = sum(1 for p in pages_to_insert if p.ollama_succeeded)
        doc.easyocr_fallback_pages = sum(1 for p in pages_to_insert if not p.ollama_succeeded)
        doc.completed_at = datetime.utcnow()

        await db.commit()

        # Auto-index into RAG
        await index_document_for_rag(document_id, result, str(user_id), db)

        await ws_manager.broadcast_to_user(str(user_id), {
            "type": "ocr_complete",
            "document_id": str(document_id),
            "total_pages": result.total_pages,
            "confidence": summary["overall_confidence"],
            "ollama_pages": doc.ollama_pages,
        })

    except Exception as exc:
        doc = await db.get(Document, document_id)
        doc.status = "failed"
        doc.error_message = str(exc)[:500]
        await db.commit()
        await ws_manager.broadcast_to_user(str(user_id), {
            "type": "ocr_error",
            "document_id": str(document_id),
            "error": str(exc),
        })
        raise
```

---

# PHASE 3 — RAG + MULTILINGUAL CHATBOT
# Model: claude-opus-4-5 | Days 6–8

**Tell Cursor:** *"Read CURSOR_PROMPT.md Phase 3. This is the most complex phase. Implement Step 3.1 completely before moving to 3.2. Use claude-opus-4-5 for this phase."*

---

## Step 3.1 — Bangla-Aware Chunker

**Why this matters for research:** Standard chunkers (LangChain, LlamaIndex) split on whitespace and sentence boundaries without understanding Bengali script. They split conjunct characters at chunk boundaries, making retrieved chunks semantically incomplete. This custom chunker is a research contribution.

`backend/app/rag/chunker.py`:
```python
"""
Bangla-aware text chunker for RAG.

Research contribution: preserves conjunct character boundaries
across chunk splits, preventing semantic fragmentation of Bengali text.
Standard chunkers (LangChain RecursiveTextSplitter) do not do this.
"""
import re
from dataclasses import dataclass
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio

BANGLA_SENTENCE_END = re.compile(r'[।\.\!\?]+\s*')
PARA_BREAK          = re.compile(r'\n{2,}')
# Hasanta (্) should never appear at the END of a chunk
# If it does, the chunk split broke a conjunct
TRAILING_HASANTA    = re.compile(r'্\s*$')


@dataclass
class Chunk:
    text:         str
    page_number:  int
    chunk_index:  int
    document_id:  str
    language:     str   # 'bn' | 'en' | 'mixed'
    char_count:   int
    word_count:   int
    has_hasanta_break: bool = False  # research quality metric


def chunk_document(
    pages: list[dict],
    chunk_size: int = 400,
    chunk_overlap: int = 80,
    document_id: str = "",
) -> list[Chunk]:
    """
    Chunk extracted pages into RAG-ready segments.

    Algorithm:
    1. Split on paragraph boundaries first (preserves document structure)
    2. Within paragraphs, split on sentence boundaries (। . ! ?)
    3. Pack sentences greedily into chunks of ~chunk_size words
    4. Overlap last N words across chunk boundaries (preserves context)
    5. Flag chunks where split broke a hasanta sequence (quality metric)

    chunk_size=400 chosen for Bengali: Bengali words are morphologically
    complex, avg 6-8 chars vs English 5. 400 Bengali words ≈ 512 tokens.
    """
    chunks: list[Chunk] = []
    chunk_idx = 0

    for page in pages:
        text = (page.get("full_text") or "").strip()
        page_num = page.get("page_number", 0)
        if not text:
            continue

        bn_ratio = bangla_char_ratio(text)
        if bn_ratio > 0.5:
            lang = "bn"
        elif bn_ratio > 0.1:
            lang = "mixed"
        else:
            lang = "en"

        for para in PARA_BREAK.split(text):
            para = para.strip()
            if not para:
                continue

            sentences = [s.strip() for s in BANGLA_SENTENCE_END.split(para) if s.strip()]
            current_words: list[str] = []
            current_size = 0

            for sentence in sentences:
                words = sentence.split()
                s_size = len(words)

                if current_size + s_size > chunk_size and current_words:
                    chunk_text = " ".join(current_words)
                    has_break = bool(TRAILING_HASANTA.search(chunk_text))
                    chunks.append(Chunk(
                        text=chunk_text,
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        document_id=document_id,
                        language=lang,
                        char_count=len(chunk_text),
                        word_count=len(current_words),
                        has_hasanta_break=has_break,
                    ))
                    chunk_idx += 1
                    # Overlap: keep last N words for context continuity
                    overlap_words = current_words[-chunk_overlap:]
                    current_words = overlap_words + words
                    current_size = len(current_words)
                else:
                    current_words.extend(words)
                    current_size += s_size

            if current_words:
                chunk_text = " ".join(current_words)
                chunks.append(Chunk(
                    text=chunk_text,
                    page_number=page_num,
                    chunk_index=chunk_idx,
                    document_id=document_id,
                    language=lang,
                    char_count=len(chunk_text),
                    word_count=len(current_words),
                ))
                chunk_idx += 1

    return chunks
```

---

## Step 3.2 — Embedder (Multilingual)

`backend/app/rag/embedder.py`:
```python
"""
Multilingual embedding for Bengali + English RAG.

Model: intfloat/multilingual-e5-large
- 560M parameters, trained on Bengali explicitly
- Dimension: 1024, MTEB multilingual retrieval score: 64.7
- Runs on M4 CPU: ~180ms per batch of 32 chunks
- Requires 'passage: ' prefix for documents, 'query: ' for queries (e5 spec)

Alternative considered: paraphrase-multilingual-mpnet-base-v2 (dim=768)
Rejected: lower Bengali recall on government document queries.
This choice is a research decision — document it in your paper.
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        # device="cpu" — MPS backend unstable for transformers on M4
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
    return _model


def embed_chunks(texts: list[str]) -> np.ndarray:
    """
    Embed document chunks. Prepend 'passage: ' per e5 paper requirement.
    Returns shape (N, 1024), L2-normalized.
    """
    model = get_embedder()
    prefixed = [f"passage: {t}" for t in texts]
    return model.encode(
        prefixed,
        batch_size=16,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def embed_query(query: str) -> np.ndarray:
    """
    Embed a user query. Prepend 'query: ' per e5 paper requirement.
    Returns shape (1024,), L2-normalized.
    """
    model = get_embedder()
    return model.encode(
        [f"query: {query}"],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
```

---

## Step 3.3 — RAG Service (ChromaDB)

`backend/app/rag/service.py`:
```python
"""
RAG service: index documents into ChromaDB, retrieve and generate answers.

Collection strategy:
- personal: user_{user_id}  — private per-user collection
- shared:   shared_corpus   — admin-curated, visible to all users

This two-tier strategy is a research contribution:
allows benchmarking personal-only vs shared+personal retrieval accuracy.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.rag.embedder import embed_chunks, embed_query
from app.rag.chunker import chunk_document, Chunk

_client: chromadb.Client | None = None


def get_chroma() -> chromadb.Client:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(settings.CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _collection_name(user_id: str, scope: str = "personal") -> str:
    return "shared_corpus" if scope == "shared" else f"user_{user_id}"


async def index_document(
    document_id: str,
    user_id: str,
    pages: list[dict],
    is_shared: bool = False,
) -> str:
    """
    Chunk pages → embed → upsert into ChromaDB.
    Returns collection name. Safe to call repeatedly (upsert).
    """
    import asyncio

    chunks = chunk_document(pages, document_id=document_id)
    if not chunks:
        return _collection_name(user_id)

    client = get_chroma()
    col_name = _collection_name(user_id, "shared" if is_shared else "personal")
    collection = client.get_or_create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,   # we supply embeddings directly
    )

    # Embed in thread (CPU-bound)
    texts = [c.text for c in chunks]
    embeddings = await asyncio.to_thread(embed_chunks, texts)

    ids       = [f"{document_id}_chunk_{c.chunk_index}" for c in chunks]
    metadatas = [{
        "document_id":  document_id,
        "page_number":  c.page_number,
        "language":     c.language,
        "chunk_index":  c.chunk_index,
        "word_count":   c.word_count,
        "has_hasanta_break": c.has_hasanta_break,  # research quality metric
    } for c in chunks]

    collection.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )

    return col_name


async def retrieve_chunks(
    query: str,
    user_id: str,
    document_ids: list[str] | None = None,
    n_results: int = 5,
    include_shared: bool = True,
) -> list[dict]:
    """
    Retrieve top-k relevant chunks from ChromaDB.
    Queries personal collection, optionally shared corpus.
    Returns list of {text, document_id, page_number, score, language}.
    """
    import asyncio

    q_embedding = await asyncio.to_thread(embed_query, query)
    client = get_chroma()
    retrieved: list[dict] = []

    def _query_collection(col_name: str, n: int, where: dict | None) -> list[dict]:
        try:
            col = client.get_or_create_collection(
                col_name, metadata={"hnsw:space": "cosine"}, embedding_function=None
            )
            results = col.query(
                query_embeddings=[q_embedding.tolist()],
                n_results=min(n, max(col.count(), 1)),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                chunks.append({
                    "text":        doc,
                    "document_id": meta["document_id"],
                    "page_number": meta["page_number"],
                    "language":    meta.get("language", "unknown"),
                    "score":       round(1.0 - dist, 4),  # cosine → similarity
                })
            return chunks
        except Exception:
            return []

    where = {"document_id": {"$in": document_ids}} if document_ids else None
    personal = await asyncio.to_thread(
        _query_collection, _collection_name(user_id), n_results, where
    )
    retrieved.extend(personal)

    if include_shared:
        shared = await asyncio.to_thread(
            _query_collection, "shared_corpus", 3, None
        )
        retrieved.extend(shared)

    retrieved.sort(key=lambda x: x["score"], reverse=True)
    return retrieved[:n_results]
```

---

## Step 3.4 — Multilingual Chatbot (Core Research Feature)

**Design principle:** The chatbot maintains a conversation history with unified context from Bangla and English documents. It detects the query language and responds in the same language. It cites sources with page numbers. It is powered by Ollama text model (not vision), so it runs fully offline.

`backend/app/chat/service.py`:
```python
"""
Multilingual document chatbot.

Unique contribution for research:
1. Unified context: retrieves from both Bengali and English document collections
2. Language-aware generation: detects query language, responds in same language
3. Cross-lingual retrieval: Bengali query can find English chunks and vice versa
   (enabled by multilingual-e5-large's cross-lingual embedding space)
4. Conversation memory: maintains N-turn history per session
5. Source attribution: every answer cites page numbers and document names
6. Graceful degradation: if Ollama offline, returns top retrieved chunks directly

Architecture: Retrieve → Rerank → Generate
- Retrieve: ChromaDB cosine similarity (multilingual embedding)
- Rerank: score = cosine_similarity × (1 + language_bonus)
  where language_bonus=0.1 if chunk.language matches query_language
- Generate: Ollama qwen2.5:7b with structured prompt
"""
import re
import httpx
from app.config import settings
from app.rag.service import retrieve_chunks
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio


def detect_language(text: str) -> str:
    """Detect if query is Bengali, English, or mixed."""
    ratio = bangla_char_ratio(text)
    if ratio > 0.3:
        return "bn"
    if ratio > 0.05:
        return "mixed"
    return "en"


def _rerank_chunks(chunks: list[dict], query_lang: str) -> list[dict]:
    """
    Rerank retrieved chunks with language affinity bonus.
    Chunks in the same language as the query get a small boost.
    This improves precision for monolingual queries.
    """
    for chunk in chunks:
        lang_bonus = 0.1 if chunk["language"] == query_lang else 0.0
        chunk["reranked_score"] = round(chunk["score"] + lang_bonus, 4)
    return sorted(chunks, key=lambda x: x["reranked_score"], reverse=True)


def _build_system_prompt(query_lang: str) -> str:
    base = (
        "You are a document analysis assistant specializing in Bengali and English "
        "government documents, university notices, and official correspondence.\n\n"
        "Rules:\n"
        "1. Answer ONLY from the provided context. Never invent facts.\n"
        "2. If the answer is not in the context, say exactly: "
        "'এই তথ্য প্রদত্ত নথিতে পাওয়া যায়নি।' (for Bengali queries) or "
        "'This information was not found in the provided documents.' (for English)\n"
        "3. Always cite your sources as [Document Name, Page N]\n"
        "4. Preserve Bengali numbers, dates, and reference numbers exactly.\n"
        "5. Do not translate between languages unless specifically asked.\n"
    )
    if query_lang == "bn":
        base += "\n6. Respond in Bengali (বাংলায় উত্তর দিন).\n"
    elif query_lang == "en":
        base += "\n6. Respond in English.\n"
    else:
        base += "\n6. Respond in the same language as the question.\n"
    return base


def _build_context_block(chunks: list[dict], doc_names: dict[str, str]) -> str:
    """Format retrieved chunks as numbered context for the LLM prompt."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        doc_name = doc_names.get(chunk["document_id"], chunk["document_id"][:20])
        parts.append(
            f"[{i}] Source: {doc_name}, Page {chunk['page_number']}\n"
            f"Relevance: {chunk['reranked_score']:.2f}\n"
            f"{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)


async def chat(
    query: str,
    user_id: str,
    session_history: list[dict],
    document_ids: list[str] | None = None,
    doc_names: dict[str, str] | None = None,
) -> dict:
    """
    Main chat handler.

    Args:
        query: User's question (Bengali or English)
        user_id: For ChromaDB collection selection
        session_history: List of {"role": "user"|"assistant", "content": "..."}
        document_ids: Optional filter to specific documents
        doc_names: {doc_id: display_name} for source citations

    Returns:
        {
          "answer": str,
          "language": "bn"|"en"|"mixed",
          "sources": [{"document_id", "document_name", "page_number", "chunk_text", "score"}],
          "model_used": str,
          "retrieved_chunks": int,
        }
    """
    query_lang = detect_language(query)
    doc_names = doc_names or {}

    # 1. Retrieve relevant chunks
    chunks = await retrieve_chunks(
        query=query,
        user_id=user_id,
        document_ids=document_ids,
        n_results=settings.RAG_TOP_K,
        include_shared=True,
    )

    # 2. Rerank with language affinity
    chunks = _rerank_chunks(chunks, query_lang)
    top_chunks = chunks[:5]

    if not top_chunks:
        no_data = (
            "কোনো প্রাসঙ্গিক তথ্য পাওয়া যায়নি। অনুগ্রহ করে আরও নথি আপলোড করুন।"
            if query_lang == "bn" else
            "No relevant documents found. Please upload more documents first."
        )
        return {"answer": no_data, "language": query_lang, "sources": [],
                "model_used": "none", "retrieved_chunks": 0}

    # 3. Build prompt
    context = _build_context_block(top_chunks, doc_names)
    system_prompt = _build_system_prompt(query_lang)

    # Build conversation for Ollama
    messages = [{"role": "system", "content": system_prompt}]

    # Add last N history turns for context continuity
    for turn in session_history[-(settings.CHAT_MAX_HISTORY):]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Current query with context
    user_content = f"Context from documents:\n\n{context}\n\nQuestion: {query}"
    messages.append({"role": "user", "content": user_content})

    # 4. Generate with Ollama text model (qwen2.5:7b — NOT vision)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.CHAT_TEXT_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 8192},
                },
            )
            resp.raise_for_status()
            answer = resp.json()["message"]["content"].strip()
            model_used = settings.CHAT_TEXT_MODEL

    except Exception as exc:
        # Graceful degradation: return top chunk text directly
        answer = (
            "মডেল সংযোগ ব্যর্থ। সবচেয়ে প্রাসঙ্গিক অনুচ্ছেদ:\n\n"
            if query_lang == "bn" else
            "Model unavailable. Most relevant passage:\n\n"
        ) + top_chunks[0]["text"]
        model_used = "fallback_direct"

    return {
        "answer": answer,
        "language": query_lang,
        "sources": [
            {
                "document_id":   c["document_id"],
                "document_name": doc_names.get(c["document_id"], "unknown"),
                "page_number":   c["page_number"],
                "chunk_text":    c["text"][:200],
                "score":         c["reranked_score"],
            }
            for c in top_chunks
        ],
        "model_used": model_used,
        "retrieved_chunks": len(top_chunks),
    }
```

`backend/app/chat/router.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_user
from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.service import chat

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Multilingual document chatbot endpoint.

    Accepts:
    {
      "query": "দুর্গাপূজার ছুটি কতদিন?",
      "session_history": [{"role": "user", "content": "..."}, ...],
      "document_ids": ["uuid1", "uuid2"],   // optional filter
      "include_shared": true
    }

    Returns:
    {
      "answer": "...",
      "language": "bn",
      "sources": [...],
      "model_used": "qwen2.5:7b",
      "retrieved_chunks": 5
    }
    """
    # Load document names for citation
    doc_names = await get_document_names(db, payload.document_ids, current_user.id)

    return await chat(
        query=payload.query,
        user_id=str(current_user.id),
        session_history=payload.session_history or [],
        document_ids=payload.document_ids,
        doc_names=doc_names,
    )
```

`backend/prompts/chat_system.txt` — system prompt for the chatbot (loaded at startup):
```
You are BanglaDOC Assistant — an expert in Bengali and English government documents.

You help researchers, university staff, and government employees find information
in uploaded PDFs including: government gazettes, university notices, scholarship
announcements, official correspondence, and policy documents.

You must:
- Answer only from the provided document context
- Cite sources as [Document Name, Page N]  
- Respond in Bengali for Bengali questions, English for English questions
- Preserve reference numbers (স্মারক নং), dates (তারিখ), and official names exactly
- For Bengali responses: use proper conjunct characters, correct দাড়ি (।)
- If information is missing: say so clearly in the appropriate language

You must never:
- Invent facts not present in the provided context
- Translate documents unless asked
- Change official names, numbers, or dates
```

---

## Step 3.5 — FastAPI Main Application

`backend/app/main.py`:
```python
from contextlib import asynccontextmanager
import asyncio
import logging
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.database import engine, Base
from app.auth.router import router as auth_router
from app.documents.router import router as docs_router
from app.rag.router import router as rag_router
from app.chat.router import router as chat_router
from app.admin.router import router as admin_router
from app.monitoring.router import router as monitoring_router
from app.websocket.manager import router as ws_router
from app.rag.embedder import get_embedder
from bangladoc_ocr.core.engine_easyocr import _init_easyocr

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Warmup EasyOCR (English reader)
    logger.info("Warming EasyOCR English reader...")
    await asyncio.to_thread(_init_easyocr)

    # Check Ollama
    ollama_ok = await _check_ollama()
    if not ollama_ok:
        logger.warning(
            "\n╔════════════════════════════════════════════╗"
            "\n║  ⚠  OLLAMA UNAVAILABLE                    ║"
            "\n║  Bangla OCR: EasyOCR fallback (~70% conf) ║"
            "\n║  Chat: will fail gracefully               ║"
            "\n║  Fix: ollama pull qwen2.5vl:7b            ║"
            "\n║       ollama serve                        ║"
            "\n╚════════════════════════════════════════════╝"
        )

    # Pre-load embedding model for RAG
    logger.info("Loading multilingual-e5-large for RAG...")
    await asyncio.to_thread(get_embedder)
    logger.info("BanglaDOC ready.")
    yield


async def _check_ollama() -> bool:
    from bangladoc_ocr import config
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                for priority in settings.OLLAMA_MODEL_PRIORITY:
                    if any(priority in m for m in models):
                        config.set_status("ollama_available", True)
                        config.set_status("ollama_model", priority)
                        logger.info("Ollama ready: %s", priority)
                        return True
                logger.warning("Ollama running, no vision model. Models: %s", models)
    except Exception as exc:
        logger.warning("Ollama unreachable: %s", exc)
    from bangladoc_ocr import config
    config.set_status("ollama_available", False)
    return False


app = FastAPI(
    title="BanglaDOC",
    description="Bangla + English PDF OCR and RAG system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,       prefix="/api/auth",      tags=["auth"])
app.include_router(docs_router,       prefix="/api/documents", tags=["documents"])
app.include_router(rag_router,        prefix="/api/rag",       tags=["rag"])
app.include_router(chat_router,       prefix="/api/chat",      tags=["chat"])
app.include_router(admin_router,      prefix="/api/admin",     tags=["admin"])
app.include_router(monitoring_router, prefix="/api",           tags=["monitoring"])
app.include_router(ws_router,         prefix="/ws",            tags=["websocket"])
```

All API routes:
```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me

GET    /api/documents
POST   /api/documents/upload
GET    /api/documents/{id}
GET    /api/documents/{id}/pages
GET    /api/documents/{id}/pages/{n}/image
GET    /api/documents/{id}/export/json
GET    /api/documents/{id}/export/txt
DELETE /api/documents/{id}

POST   /api/rag/query
GET    /api/rag/collections
POST   /api/rag/index/{doc_id}

POST   /api/chat          ← multilingual chatbot

GET    /api/status        ← engine health
GET    /api/corpus/stats

GET    /api/admin/users
PATCH  /api/admin/users/{id}/quota
POST   /api/admin/corpus/share/{doc_id}

WS     /ws/progress/{user_id}?token=...
```

---

# PHASE 4 — FRONTEND
# Model: claude-sonnet-4-5 | Days 9–12

**Tell Cursor:** *"Read CURSOR_PROMPT.md Phase 4. Build the frontend using the exact design tokens specified. Do not use shadcn/ui or any component library."*

---

## Step 4.1 — Vite + TypeScript Setup

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install react-router-dom @tanstack/react-query @tanstack/react-table zustand axios framer-motion react-dropzone lucide-react clsx tailwind-merge
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

`frontend/index.html` — critical: load Bengali font:
```html
<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BanglaDOC</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Noto+Sans+Bengali:wght@400;500&display=swap" rel="stylesheet">
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

`frontend/src/styles/globals.css` — design tokens:
```css
:root {
  --bg:         #0C0C0B;
  --bg-2:       #141412;
  --bg-3:       #1C1C19;
  --bg-4:       #242420;
  --line:       rgba(255,255,255,0.07);
  --line-2:     rgba(255,255,255,0.12);
  --text:       #F0EBE0;
  --text-2:     #9E9880;
  --text-3:     #5C5A4E;
  --amber:      #D4A847;
  --amber-dim:  rgba(212,168,71,0.12);
  --amber-glow: rgba(212,168,71,0.06);
  --green:      #4CAF82;
  --green-dim:  rgba(76,175,130,0.12);
  --red:        #E05252;
  --red-dim:    rgba(224,82,82,0.10);
  --blue:       #5B9BD5;
  --blue-dim:   rgba(91,155,213,0.12);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; background: var(--bg); color: var(--text); }
body { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; line-height: 1.5; }

/* Bengali text — always use Noto Sans Bengali */
.bangla-text {
  font-family: 'Noto Sans Bengali', 'IBM Plex Sans', sans-serif;
  font-size: 14px;
  line-height: 2.0;
}

/* Monospace for technical values */
.mono { font-family: 'IBM Plex Mono', monospace; }

/* Headings */
.display { font-family: 'DM Serif Display', serif; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: var(--bg-4); border-radius: 3px; }
```

---

## Step 4.2 — Page Specifications

**`Dashboard.tsx`**
- Stats row: Total Documents, Pages Extracted, Avg Confidence, Corpus Words
- Document table with columns: Name | Language pill | Pages | Confidence bar | Engine badge | Status
- Engine badges: `ollama:qwen2.5vl:7b` = amber, `PyMuPDF` = green, `easyocr_fallback` = red with ↓
- Quick upload zone in right panel
- EngineStatusBar component (Ollama warning if offline)

**`Upload.tsx`**
- Large drag-drop zone
- Domain selector dropdown: Government Notice | Gazette | Academic | Financial | General
- Processing mode: Auto | Ollama primary | EasyOCR only
- Ollama status info box (green if available, amber warning if not)
- After upload: real-time progress from WebSocket
- Show per-page engine being used (pulsing indicator)

**`DocumentViewer.tsx`**
- Split 50/50: left = rendered page image (`<img src="/api/documents/{id}/pages/{n}/image">`), right = extracted text
- ConfidenceRing component (SVG circle, color = tier)
- Page navigation (prev/next arrows)
- TextAnnotated component: renders extracted text with inline red annotations where Stage F fixed artifacts
- All Bengali text must use `className="bangla-text"` (Noto Sans Bengali)
- Block list below: shows each ContentBlock with type + confidence
- Export buttons: Copy text | Download .txt | Download .json

**`Chat.tsx`** (Most complex — use claude-opus-4-5 for this)
- Top: CollectionPicker — checkboxes for which documents to include in context
- Left sidebar: conversation sessions list
- Center: chat window
  - User messages (right-aligned, amber tint background)
  - Assistant messages (left-aligned, dark card)
  - Each assistant message has expandable Sources section
  - Source card: document name + page number + clickable → opens DocumentViewer
  - Language indicator on each message (বাংলা / English / Mixed)
- Bottom: input box with send button
  - Placeholder alternates: "বাংলায় প্রশ্ন করুন..." and "Ask in English..."
  - Language auto-detected as you type (show flag indicator)
- Loading state: "উত্তর খুঁজছি..." (searching for answer) pulsing

**`EngineStatusBar.tsx`** — shown in sidebar:
```tsx
// Three rows: Ollama, EasyOCR, Gemini
// If Ollama offline → amber warning banner appears at top of all pages:
// "⚠ Ollama offline — Bangla quality reduced (~70%). Run: ollama serve"
// Polls /api/status every 30 seconds
```

---

# PHASE 5 — RESEARCH POLISH
# Model: claude-opus-4-5 | Days 13–14

**Tell Cursor:** *"Read CURSOR_PROMPT.md Phase 5. Generate the benchmark script and README."*

---

## Step 5.1 — Benchmark Script (Research Paper Data)

`backend/scripts/benchmark.py` — run all 8 known PDFs, save results:

```python
"""
Research benchmark — generates data for paper ablation study.
Run: python scripts/benchmark.py path/to/test_pdfs/

Outputs:
  data/benchmark_runs.jsonl — raw per-doc metrics
  data/benchmark_summary.json — aggregated table for paper

This generates Table 2 in the research paper:
"OCR Engine Comparison on Government Bengali Documents"
"""
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from bangladoc_ocr.pipeline import process_pdf
from bangladoc_ocr import config

KNOWN_DOCS = {
    "notice_durga_puja":    {"type": "scanned_bangla_notice",     "pages": 1},
    "Image_001":            {"type": "scanned_bangla_scholarship", "pages": 1},
    "b89c4883":             {"type": "scanned_bangla_gazette",     "pages": 1},
    "forwarding":           {"type": "scanned_bangla_forwarding",  "pages": 2},
    "Freedom_Fight":        {"type": "scanned_bangla_mixed",       "pages": 2},
    "WEF_barometer":        {"type": "digital_english_report",     "pages": 26},
    "bangla_academy":       {"type": "digital_bijoy_font",         "pages": 1},
    "corporate_loan":       {"type": "scanned_bangla_form",        "pages": 2},
}

if __name__ == "__main__":
    pdf_dir = Path(sys.argv[1])
    output_path = Path("data/benchmark_runs.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ollama_status = config.get_status().get("ollama_available")
    print(f"Ollama available: {ollama_status}")
    print(f"Ollama model: {config.get_status().get('ollama_model')}")
    print("-" * 60)

    runs = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        t0 = time.time()
        try:
            result = process_pdf(str(pdf), use_multiprocessing=False)
            elapsed = time.time() - t0
            summary = result.to_dict()["document"]["processing_summary"]

            pages_data = result.to_dict()["pages"]
            ollama_pages = sum(
                1 for p in pages_data
                if any(d.get("keyword") == "OLLAMA_SUCCESS"
                       for d in p.get("decisions", []))
            )
            stage_f_fixes = sum(
                p.get("log", {}).get("stage_f_fixes", 0)
                for p in result.pages
            )
            bijoy_detected = any(
                p.get("log", {}).get("bijoy_detected", False)
                for p in result.pages
            )

            run = {
                "doc_name":          pdf.stem,
                "doc_type":          KNOWN_DOCS.get(pdf.stem, {}).get("type", "unknown"),
                "total_pages":       result.total_pages,
                "overall_confidence": summary["overall_confidence"],
                "processing_time_s": round(elapsed, 1),
                "time_per_page_s":   round(elapsed / max(result.total_pages, 1), 1),
                "ollama_pages":      ollama_pages,
                "easyocr_fallback":  result.total_pages - ollama_pages,
                "stage_f_fixes":     stage_f_fixes,
                "bijoy_detected":    bijoy_detected,
                "language":          result.language_detected,
                "ollama_model":      config.get_status().get("ollama_model", "none"),
            }
            runs.append(run)

            status = "✓" if run["overall_confidence"] > 0.75 else "⚠"
            print(
                f"{status} {pdf.stem[:30]:<30} | "
                f"conf={run['overall_confidence']:.3f} | "
                f"time={run['processing_time_s']}s | "
                f"ollama={ollama_pages}/{result.total_pages} pages | "
                f"stageF={stage_f_fixes} fixes"
            )

        except Exception as exc:
            print(f"✗ {pdf.stem}: FAILED — {exc}")

    with open(output_path, "w", encoding="utf-8") as f:
        for run in runs:
            f.write(json.dumps(run, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(runs)} runs to {output_path}")

    # Summary statistics
    if runs:
        avg_conf = sum(r["overall_confidence"] for r in runs) / len(runs)
        bangla_runs = [r for r in runs if "bangla" in r["doc_type"]]
        avg_bangla = sum(r["overall_confidence"] for r in bangla_runs) / len(bangla_runs) if bangla_runs else 0
        print(f"\nSummary:")
        print(f"  Avg confidence (all): {avg_conf:.3f}")
        print(f"  Avg confidence (Bangla): {avg_bangla:.3f}")
        print(f"  Total Stage F fixes: {sum(r['stage_f_fixes'] for r in runs)}")
```

---

## Step 5.2 — Research Paper Outline

Your paper title: **"BanglaDOC: A Confidence-Tier-Aware Hybrid OCR and Retrieval-Augmented Generation System for Bengali Government Documents"**

**Section outline:**
1. Introduction — digitisation gap for Bengali gov docs, no existing RAG system
2. Related Work — existing Bengali OCR (EasyOCR, PaddleOCR), existing RAG systems, why neither alone is sufficient
3. System Architecture — figure of the full pipeline (OCR → Corpus → RAG → Chat)
4. OCR Pipeline — language detection fast-path, Bijoy font detection, Stage F corrections, confidence tiers
5. RAG Design — Bangla-aware chunking (conjunct preservation), multilingual-e5-large selection rationale, two-tier collection strategy
6. Multilingual Chatbot — language detection, cross-lingual retrieval, reranking with language affinity bonus
7. Experiments — Table 1: OCR quality by engine (EasyOCR vs Ollama), Table 2: confidence tier distribution, Table 3: RAG recall@5 by confidence tier, Figure 1: processing time comparison
8. Results and Discussion
9. Limitations — M4 hardware dependency, Ollama model availability
10. Conclusion + Future Work

**Unique claims for paper:**
- First Bengali government document RAG system with per-page engine attribution
- Bijoy font early detection algorithm (prevents 478s processing loops)
- Stage F EasyOCR artifact cleanup (7 confirmed patterns from real government docs)
- Bangla-aware chunking with hasanta boundary preservation
- Cross-lingual retrieval for Bengali+English mixed document corpora

---

## Step 5.3 — Makefile

```makefile
.PHONY: dev db-up db-down migrate seed test benchmark check-ollama

dev:
	make -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python scripts/seed_db.py

test:
	cd backend && pytest tests/ -v --tb=short

benchmark:
	cd backend && python scripts/benchmark.py ../test_pdfs/

check-ollama:
	@curl -s http://localhost:11434/api/tags | \
	  python3 -c "import json,sys; d=json.load(sys.stdin); \
	  [print('✓', m['name']) for m in d.get('models',[])]" \
	  || echo "✗ Ollama not running — run: ollama serve"

phase1-verify:
	@echo "Verifying Phase 1 OCR fixes..."
	cd backend && python3 -c "
from bangladoc_ocr.nlp.unicode_validator import validate_digital_text
from bangladoc_ocr.nlp.bangla_corrector import fix_easyocr_artifacts
text = 'বাংনা সাহঢ 81[64]47 paruaacademirogmail.con ' * 15
ok, rep = validate_digital_text(text)
assert not ok and rep.get('bijoy_detected'), 'Bijoy fix FAILED'
fixed, changed = fix_easyocr_artifacts('নিজ্ঞপ্তি ছিল| বুলনা ১০২৬')
assert 'বিজ্ঞপ্তি' in fixed, 'Stage F fix FAILED'
assert '।' in fixed, 'Pipe→danda FAILED'
assert '২০২৬' in fixed, 'Year fix FAILED'
print('✓ All Phase 1 fixes verified')
"
```

---

## COMPLETE API CONTRACT (for frontend dev)

```typescript
// All types for frontend API client

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

interface DocumentSummary {
  id: string
  original_filename: string
  total_pages: number
  language_detected: string[]
  overall_confidence: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  domain: string
  is_indexed_rag: boolean
  ollama_pages: number
  easyocr_fallback_pages: number
  processing_time_ms: number
  created_at: string
}

interface PageResponse {
  page_number: number
  full_text: string
  engine_used: string
  confidence_score: number
  confidence_tier: 'gold' | 'silver' | 'bronze'
  language_ratio_bn: number
  word_count: number
  artifact_corrections: number
  ollama_succeeded: boolean
  verified: boolean
}

interface ChatRequest {
  query: string
  session_history: Array<{role: 'user' | 'assistant', content: string}>
  document_ids?: string[]
  include_shared?: boolean
}

interface ChatResponse {
  answer: string
  language: 'bn' | 'en' | 'mixed'
  sources: Array<{
    document_id: string
    document_name: string
    page_number: number
    chunk_text: string
    score: number
  }>
  model_used: string
  retrieved_chunks: number
}

interface EngineStatus {
  engines: {
    ollama: { available: boolean, model: string | null }
    easyocr: { available: boolean }
    gemini: { available: boolean, enabled: boolean }
  }
  warning: string | null
}

// WebSocket messages
type WSMessage =
  | { type: 'ocr_progress', document_id: string, current_page: number, total_pages: number, percent: number }
  | { type: 'ocr_complete', document_id: string, total_pages: number, confidence: number, ollama_pages: number }
  | { type: 'ocr_error', document_id: string, error: string }
  | { type: 'ping' }
```

---

## FINAL CHECKLIST

Before submitting for research:

**OCR Quality:**
- [ ] Bijoy font PDF processes in < 40s (was 478s)
- [ ] All Bangla scanned docs show OLLAMA_SUCCESS in decisions (requires Ollama running)
- [ ] Stage F corrections appear in extraction logs
- [ ] Smarak numbers are Bengali-only digits
- [ ] Year digits are ২০XX not ১০XX

**RAG:**
- [ ] Bengali query retrieves correct chunks from Bengali documents
- [ ] English query retrieves correct chunks from English documents
- [ ] Bengali query retrieves from English documents (cross-lingual test)
- [ ] Source citations include correct page numbers

**Chat:**
- [ ] Bengali question → Bengali answer
- [ ] English question → English answer  
- [ ] Mixed query → appropriate language response
- [ ] Sources displayed and clickable
- [ ] Graceful degradation when Ollama offline

**Research Data:**
- [ ] `benchmark_runs.jsonl` exists with all 8 documents
- [ ] Before/after confidence scores documented
- [ ] Engine attribution per page in DB
- [ ] hasanta break count per chunk tracked

---

*This is the final authoritative prompt. All previous versions (V1, V2, V3) are superseded.*
*Apply Phase 1 first. Verify with `make phase1-verify`. Then proceed to Phase 2.*
*Never ask Cursor to implement multiple phases simultaneously.*
