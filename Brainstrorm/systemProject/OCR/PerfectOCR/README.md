# ⚡ TurbOCR v3.0 — Ultra-Fast PDF OCR System

> **Native PDF → Gemini AI → Structured JSON in seconds**  
> Supports Bangla & English • Tables • Handwriting • Multiple PDFs

---

## 🚀 What is TurbOCR?

TurbOCR is a high-performance OCR system that extracts text from PDF documents using **native PDF upload to Google Gemini AI**. Unlike traditional OCR pipelines that convert pages to images first, TurbOCR sends the raw PDF directly — achieving **4.3× less token usage** and **10-20× fewer API calls**.

### Key Numbers

| Metric                   | TurbOCR v3.0 | Traditional (Image-based) |
| ------------------------ | ------------ | ------------------------- |
| **Tokens/page**          | 258          | 1,120+                    |
| **API calls (10 pages)** | 1            | 10-20                     |
| **Time per page**        | ~1-2s        | ~3-8s                     |
| **Cost per 100 pages**   | ~$0.02       | ~$0.15+                   |
| **Max pages**            | 1,000        | Limited by time           |
| **Max file size**        | 50 MB        | N/A                       |

---

## 📦 Project Structure

```
PerfectOCR/
├── turbo_app.py          # 🖥️  Streamlit UI — main entry point
├── turbo_pipeline.py     # ⚡  TurbOCR engine (native PDF + parallel fallback)
├── config.py             # ⚙️  Central configuration (API keys, models, paths)
├── pipeline.py           # 🔬  Legacy pipeline (image-based, dual-model)
├── ocr_engines.py        # 🧠  Gemini & GPT-4o OCR engines + MASTER_PROMPT
├── fast_ocr.py           # 🏃  Tesseract local OCR (free, English bypass)
├── merger.py             # 🔗  Merge Gemini + GPT-4o results
├── correction.py         # 🔧  Bangla text post-correction
├── models.py             # 📊  Data models (ContentBlock, PageResult, etc.)
├── pdf_processor.py      # 📄  PDF → image conversion (PyMuPDF)
├── output_handler.py     # 💾  JSON save/export
├── requirements.txt      # 📋  Python dependencies
├── FLOWCHART.html        # 📐  Interactive pipeline flowchart
└── __init__.py           # 📦  Package init (v3.0.0)
```

---

## 🛠️ Installation

### Prerequisites

- **Python 3.10+**
- **Gemini API Key** (required) — [Get one here](https://aistudio.google.com/apikey)
- **OpenAI API Key** (optional, for legacy pipeline fallback)
- **Tesseract** (optional, for free English OCR bypass)

### Setup

```bash
# 1. Navigate to project
cd PerfectOCR

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API keys in .env file (in parent directory)
echo GEMINI_API_KEY=your_key_here > ..\.env
echo OPENAI_API_KEY=your_key_here >> ..\.env   # Optional
```

### Tesseract (Optional)

Tesseract provides free local OCR for simple English documents, skipping API calls entirely.

- **Path configured**: `D:\3-2\Ollama\tesseract.exe`
- If installed elsewhere, update path in `fast_ocr.py`

---

## 🚀 Quick Start

### Run the Streamlit Dashboard

```bash
streamlit run PerfectOCR/turbo_app.py
```

This opens a clean web UI where you:

1. **Drop PDF files** (multiple supported)
2. Wait for auto-processing
3. **Download results** as JSON or plain text

No configuration needed — everything is optimized by default.

### Use from Python

```python
from PerfectOCR.turbo_pipeline import turbo_ocr, turbo_ocr_batch

# Single PDF
result = turbo_ocr("document.pdf")
print(result.get_full_text())
print(f"Pages: {result.total_pages}, API calls: {result.api_calls}")

# Multiple PDFs
results = turbo_ocr_batch(["doc1.pdf", "doc2.pdf", "doc3.pdf"])
for name, result in results.items():
    print(f"{name}: {result.total_pages} pages in {result.processing_time_ms:.0f}ms")
```

### Use with Progress Callback

```python
from PerfectOCR.turbo_pipeline import turbo_ocr

def on_progress(current, total, status):
    print(f"[{current}/{total}] {status}")

result = turbo_ocr("large_document.pdf", progress_callback=on_progress)
```

---

## 🔄 Pipeline Flow

### TurbOCR v3.0 (Primary — Recommended)

```
User uploads PDF(s)
    │
    ▼
Save to temp directory
    │
    ▼
TurboOCREngine initializes (lazy Gemini client)
    │
    ▼
fitz.open() → get page count (instant, no conversion)
    │
    ▼
Upload PDF to Gemini Files API (native binary, cached)
    │  ← 258 tokens/page (vs 1120+ for images)
    ▼
ONE API call: generate_content(file + prompt) for ALL pages
    │
    ├── SUCCESS → Parse JSON response → PageOCRResult per page
    │
    └── FAILURE → Parallel fallback:
                   ThreadPoolExecutor(5 workers)
                   Each page → JPEG 85% @ 200 DPI → Gemini
    │
    ▼
DocumentOCRResult (filename, pages[], stats)
    │
    ▼
Streamlit display: stats, download, per-file results
    │
    ▼
Cleanup temp files
```

### Legacy Pipeline (pipeline.py)

```
PDF → Images (250 DPI, PyMuPDF)
    │
    ▼
Per page:
    ├── Tesseract check (if available)
    │   ├── Good enough → Use (FREE, no API)
    │   └── Need AI → Continue
    │
    ├── Strategy: gemini_primary (default)
    │   ├── Gemini OCR → Success → Use
    │   └── Fail → GPT-4o fallback
    │
    ├── Strategy: dual
    │   ├── Both Gemini + GPT-4o
    │   └── Merge: Gemini primary, GPT-4o for low-confidence
    │
    ▼
Bangla Correction (full text + low-confidence blocks)
    │
    ▼
Save JSON (per-page + merged document)
```

### View Full Flowchart

Open `FLOWCHART.html` in a browser for an interactive, detailed visualization of the entire pipeline.

---

## ⚙️ Configuration

All settings in `config.py`:

| Setting                    | Value              | Description                        |
| -------------------------- | ------------------ | ---------------------------------- |
| `GEMINI_MODEL`             | `gemini-2.5-flash` | Primary OCR model                  |
| `OPENAI_MODEL`             | `gpt-4o`           | Fallback OCR model                 |
| `DEFAULT_STRATEGY`         | `gemini_primary`   | OCR strategy for legacy pipeline   |
| `DPI`                      | `250`              | Image resolution (legacy pipeline) |
| `CORRECTION_MODEL`         | `gemini-2.5-flash` | Bangla text correction model       |
| `ENABLE_BANGLA_CORRECTION` | `True`             | Enable Bangla post-correction      |
| `MAX_PDF_SIZE_MB`          | `50`               | Maximum PDF file size              |
| `CACHE_ENABLED`            | `True`             | Enable result caching              |

API keys are loaded from `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key      # Optional
OPENAI_BASE_URL=                          # Optional (for Azure/Copilot)
```

---

## 📊 Output Format

### TurbOCR Output (DocumentOCRResult)

```json
{
  "document": {
    "filename": "notice.pdf",
    "total_pages": 3,
    "processing_time_ms": 4521.3,
    "api_calls": 1
  },
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        {
          "id": 1,
          "type": "header",
          "lang": "bn",
          "text": "কুয়েট বিজ্ঞপ্তি",
          "conf": "high",
          "handwritten": false
        }
      ],
      "tables": [
        {
          "id": 1,
          "data": [
            ["ক্রমিক", "নাম", "বিভাগ"],
            ["১", "মোঃ আলম", "CSE"]
          ]
        }
      ],
      "full_text": "কুয়েট বিজ্ঞপ্তি\nতারিখ: ২৮/০৯/২০২৩\n...",
      "notes": [],
      "processing_time_ms": 1500.2,
      "source": "gemini-native"
    }
  ]
}
```

### Block Types

| Type        | Description                                |
| ----------- | ------------------------------------------ |
| `header`    | Document headers, titles                   |
| `paragraph` | Body text, descriptions                    |
| `list`      | Ordered/unordered lists                    |
| `table`     | Tabular data (with `data` field)           |
| `image`     | Visual elements (described, not "[IMAGE]") |
| `signature` | Handwritten signatures                     |

---

## 🧠 OCR Capabilities

### Bengali (বাংলা) Support

- **Bengali numerals** (০১২৩৪৫৬৭৮৯): 6-step extraction protocol with visual verification
- **Mattra/hasanta/conjunct**: Preserved exactly as written
- **Date validation**: Month ≤ 12, Day ≤ 31 checks
- **Post-correction**: Fixes common OCR errors in Bengali text

### Common Bengali Numeral Confusion Pairs

| Often Confused | Visual Difference                 |
| -------------- | --------------------------------- |
| ৩ ↔ ৫          | ৩ = curved top, ৫ = flat top bar  |
| ৮ ↔ ৪          | ৮ = two loops, ৪ = one open curve |
| ৬ ↔ ৯          | ৬ = curves left, ৯ = curves right |
| ২ ↔ ৩          | ২ = one belly, ৩ = two bellies    |

### Document Features

- ✅ Printed text (Bangla + English)
- ✅ Handwritten text & signatures
- ✅ Tables (multi-row, multi-column, merged cells)
- ✅ Forms (labels + filled values)
- ✅ Images, logos, seals (described in text)
- ✅ Multi-column layouts
- ✅ Headers, footers, page numbers
- ✅ Stamps, watermarks

---

## 🏗️ Architecture Decisions

### Why Native PDF Upload?

The Gemini Files API accepts raw PDF binary, which is **4.3× more token-efficient** than sending page images:

- **258 tokens/page** (native PDF) vs **1,120+ tokens/page** (PNG image)
- No image conversion step — saves CPU time and memory
- Single API call for entire document (up to 1,000 pages)
- Supports PDFs up to 50 MB

### Why Parallel Fallback?

If native PDF processing fails (network error, API issue, malformed PDF):

- **ThreadPoolExecutor** with 5 concurrent workers
- Each page: render to **JPEG 85%** at **200 DPI** (smaller than PNG @ 250 DPI)
- Independent per-page Gemini API calls
- Graceful error handling — failed pages don't block others

### Why Tesseract + AI Hybrid?

For the legacy pipeline, simple English-only pages don't need expensive AI:

- **Tesseract** runs locally (FREE, no API cost)
- `should_use_ai_ocr()` checks: confidence, character set, text length
- Only calls Gemini/GPT-4o when Tesseract isn't sufficient
- Bangla text always routes to AI (Tesseract can't handle it well)

---

## 📋 Requirements

```
PyMuPDF>=1.24.0          # PDF processing (fitz)
google-genai>=1.0.0      # Gemini AI (primary OCR)
openai>=1.0.0            # GPT-4o (fallback, optional)
streamlit>=1.30.0        # Web dashboard
python-dotenv>=1.0.0     # .env file loading
Pillow>=10.0.0           # Image processing
# pytesseract            # Optional: local OCR bypass
```

---

## 🔗 Related Files

- **Flowchart**: Open `FLOWCHART.html` in a browser for interactive pipeline visualization
- **Config**: Edit `config.py` for API keys, model selection, DPI, etc.
- **Prompts**: OCR prompts are in `turbo_pipeline.py` (TURBO_PROMPT) and `ocr_engines.py` (MASTER_PROMPT)

---

## 📜 Version History

| Version  | Highlights                                                                 |
| -------- | -------------------------------------------------------------------------- |
| **v3.0** | TurbOCR: Native PDF upload, 1 API call/doc, multi-file upload, clean UI    |
| **v2.0** | Tesseract hybrid, Bengali numeral protocol, auto-strategy, Streamlit fixes |
| **v1.0** | Dual-model (Gemini + GPT-4o), Bangla correction, structured JSON output    |

---

<p align="center">
<strong>TurbOCR v3.0</strong> — Built with Gemini 2.5 Flash • PyMuPDF • Streamlit<br>
Native PDF processing → 258 tokens/page → 1 API call per document
</p>
