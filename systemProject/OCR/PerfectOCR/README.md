# 🔬 PerfectOCR — Dual-Model OCR System

Production-grade PDF OCR using **GPT-4o + Gemini** for mixed Bangla/English documents with structured JSON output.

## Architecture

```
PDF Upload
  │
  ▼
┌─────────────────────────────┐
│  PDF → Images (PyMuPDF)     │
│  200 DPI per page           │
└──────────┬──────────────────┘
           │
           ▼
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐  ┌─────────┐
│ GPT-4o │  │ Gemini  │
│  OCR   │  │  OCR    │
└───┬────┘  └────┬────┘
    │            │
    ▼            ▼
┌─────────────────────────────┐
│  Merge / Vote               │
│  • Low-conf blocks → swap   │
│  • Tables → pick most data  │
│  • Forms → pick most filled │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Bangla Correction Pass     │
│  Fix mattra/hasanta/conjunct│
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Structured JSON Output     │
│  content_blocks, tables,    │
│  forms, full_text           │
└─────────────────────────────┘
```

## Directory Structure

```
PerfectOCR/
├── __init__.py          # Package init
├── config.py            # Configuration & API keys
├── models.py            # Data models (ContentBlock, PageResult, DocumentResult)
├── pdf_processor.py     # PDF → Images (PyMuPDF)
├── ocr_engines.py       # Gemini + GPT-4o OCR engines
├── merger.py            # Result merging / voting
├── correction.py        # Bangla text post-correction
├── pipeline.py          # Main orchestrator
├── output_handler.py    # JSON output saving
├── app.py               # Streamlit dashboard
├── main.py              # CLI entry point
└── requirements.txt     # Dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r PerfectOCR/requirements.txt
```

### 2. Set API Keys

Add to your `.env` file:

```
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

### 3. Run Streamlit Dashboard

```bash
streamlit run PerfectOCR/app.py
```

### 4. Run via CLI

```bash
# Dual mode (both models)
python -m PerfectOCR.main document.pdf

# GPT-4o only
python -m PerfectOCR.main document.pdf --strategy gpt4o_only

# Gemini only
python -m PerfectOCR.main document.pdf --strategy gemini_only

# High quality, no correction
python -m PerfectOCR.main document.pdf --dpi 300 --no-correction
```

## OCR Strategies

| Strategy           | Description                      | API Calls | Best For         |
| ------------------ | -------------------------------- | --------- | ---------------- |
| **dual**           | Both models → merge best results | 2x pages  | Maximum accuracy |
| **gpt4o_primary**  | GPT-4o first → Gemini fallback   | 1-2x      | Cost-quality     |
| **gemini_primary** | Gemini first → GPT-4o fallback   | 1-2x      | Cost-quality     |
| **gpt4o_only**     | GPT-4o only                      | 1x        | Speed/cost       |
| **gemini_only**    | Gemini only                      | 1x        | Speed/cost       |

## Output JSON Schema

```json
{
  "document": {
    "source": "document.pdf",
    "total_pages": 3,
    "language_detected": ["bn", "en"],
    "has_handwriting": true,
    "has_tables": true,
    "has_images": false,
    "has_forms": false,
    "models_used": ["gemini-2.5-flash", "gpt-4o"]
  },
  "pages": [
    {
      "page_number": 1,
      "content_blocks": [
        {
          "block_id": 1,
          "type": "header",
          "position": "top",
          "language": "bn",
          "confidence": "high",
          "text": "শিরোনাম",
          "is_handwritten": false,
          "_source": "gpt4o"
        }
      ],
      "tables": [...],
      "forms": [...],
      "full_text_reading_order": "...",
      "extraction_notes": [...]
    }
  ],
  "extraction_notes": []
}
```

## Key Features

- **Dual-model OCR**: GPT-4o + Gemini for maximum Bangla accuracy
- **Smart merging**: Per-block voting — swaps low-confidence blocks
- **Bangla-first**: Preserves every mattra, hasanta, nukta, and conjunct
- **Structured output**: Tables, forms, headers, footers, handwriting
- **Post-correction**: LLM-based Bangla error fixing
- **Streamlit UI**: Upload, process, preview, and download
- **CLI support**: Batch processing from command line
