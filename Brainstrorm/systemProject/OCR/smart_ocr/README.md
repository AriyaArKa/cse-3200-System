# 🧠 Smart OCR System

Production-grade PDF OCR with **Bangla-first accuracy**, cost optimization, and backward-compatible JSON output.

## Architecture Overview

```
PDF Upload
  │
  ▼
┌──────────────────────────────────┐
│  Page Classification             │
│  (Native text? Scanned image?)   │
└──────┬───────────┬───────────────┘
       │           │
   Has text    No text
       │           │
       ▼           ▼
┌──────────┐  ┌──────────────┐
│  Native  │  │  Convert to  │
│  Extract │  │  Image (only │
│  (PyMuPDF│  │  this page)  │
│  )       │  └──────┬───────┘
└────┬─────┘         │
     │               ▼
     │         ┌──────────────┐
     │         │  PaddleOCR   │
     │         │  (Bangla+EN) │
     │         └──────┬───────┘
     │                │
     ▼                ▼
┌─────────────────────────────────┐
│  Block Segmentation             │
│  (Split into paragraphs)        │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Per-Block Processing:          │
│  1. Language Detection          │
│  2. Confidence Scoring          │
│  3. Routing Decision            │
│     ├─ HIGH → Accept            │
│     ├─ MEDIUM → Correction      │
│     └─ LOW → Gemini (block only)│
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Merge & Output                 │
│  JSON (old format compatible)   │
└─────────────────────────────────┘
```

## Directory Structure

```
smart_ocr/
├── __init__.py              # Package init
├── config.py                # All configuration & thresholds
├── models.py                # Data models (Block, PageResult, DocumentResult)
├── pdf_processor.py         # Smart PDF processing (native text first)
├── ocr_engine.py            # PaddleOCR wrapper (Bangla + English)
├── language_detector.py     # Language detection (Bangla/English/Mixed)
├── confidence_scorer.py     # Composite confidence scoring
├── correction_layer.py      # Pre-Gemini correction (spell, unicode, matra)
├── gemini_fallback.py       # Gemini API (block-level only, cached)
├── block_router.py          # Block-level intelligent routing
├── output_handler.py        # JSON output (old format compatible)
├── pipeline.py              # Main orchestrator
├── app.py                   # Streamlit dashboard
├── main.py                  # CLI entry point
└── requirements.txt         # Dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r smart_ocr/requirements.txt
```

### 2. Set API Key

Add to your `.env` file:

```
GEMINI_API_KEY=your_key_here
```

### 3. Run via CLI

```bash
# Smart mode (recommended)
python -m smart_ocr.main document.pdf

# Gemini-only mode (like old method)
python -m smart_ocr.main document.pdf --mode gemini

# Custom output directory
python -m smart_ocr.main document.pdf --output-dir ./results
```

### 4. Run via Streamlit Dashboard

```bash
streamlit run smart_ocr/app.py
```

## Processing Modes

| Mode            | Description                                                           | Cost    |
| --------------- | --------------------------------------------------------------------- | ------- |
| **Smart**       | Native text first → PaddleOCR → Gemini for low-confidence blocks only | Lowest  |
| **PaddleOCR**   | PaddleOCR for all image pages, Gemini fallback                        | Medium  |
| **Gemini Only** | All pages → images → Gemini (old method)                              | Highest |

## Output Format

Output JSON is **backward compatible** with the old system:

```json
{
  "pages": [
    {
      "source_file": "page_1.json",
      "data": {
        "text_blocks": ["..."],
        "full_text": "...",
        "_metadata": {
          "source_type": "native_text",
          "confidence": 0.92,
          "language_distribution": {"bangla": 0.8, "english": 0.2},
          "gemini_blocks": 0,
          "total_blocks": 3
        }
      }
    }
  ],
  "_document_metadata": {
    "overall_confidence": 0.89,
    "gemini_usage_summary": {...},
    "language_distribution_summary": {...}
  }
}
```

## Key Features

- **Bangla-first**: Stricter confidence thresholds for Bangla text
- **Smart routing**: Never blindly converts all pages to images
- **Block-level Gemini**: Only sends low-confidence blocks, not full pages
- **Cost-efficient**: Caching, native extraction, minimal API calls
- **Correction layer**: Fixes common OCR errors before Gemini
- **Confidence scoring**: Weighted formula with 6 signals
- **Old-format JSON output**: Drop-in replacement for existing system
