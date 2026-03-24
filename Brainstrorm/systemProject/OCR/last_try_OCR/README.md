# Last-Try OCR

## 1) What This System Does
Last-Try OCR processes Bangla + English PDF documents using a hybrid pipeline: direct digital text extraction when possible, and OCR fallback when needed. It combines local OCR engines with optional Gemini/Ollama fallback for difficult pages, then writes structured JSON outputs and an additional research-ready corpus export.

## 2) Quick Start
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m last_try_OCR.app
```

Run API server explicitly with uvicorn:
```bash
uvicorn last_try_OCR.app:app --host 0.0.0.0 --port 8000 --reload
```

## 3) How To Use The Web UI
1. Start the FastAPI server.
2. Open `http://localhost:8000/` in your browser.
3. Drag/drop a PDF, choose a domain (`newspaper`, `govt`, `academic`, `unknown`), then click **Upload & OCR**.
4. Watch page progress, review extracted text page-by-page, and mark pages as verified.
5. Use **Corpus Stats** and **Download Corpus** from the bottom panel.

## 4) How To Use The CLI (`main.py`)
```bash
python -m last_try_OCR.main sample.pdf
python -m last_try_OCR.main sample.pdf another.pdf --no-mp
python -m last_try_OCR.main sample.pdf --verbose
```

## 5) How To Use The API
OCR upload (with domain):
```bash
curl -X POST "http://localhost:8000/ocr" \
  -F "files=@/absolute/path/document.pdf" \
  -F "domain=govt"
```

Read corpus stats:
```bash
curl "http://localhost:8000/corpus/stats"
```

Download corpus parquet:
```bash
curl -L "http://localhost:8000/corpus/export" -o bangla_ocr_corpus.parquet
```

Mark a page as verified:
```bash
curl -X POST "http://localhost:8000/corpus/verify" \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"document_ab12cd34","page_number":1,"verified":true}'
```

## 6) Configuration (`.env`)
- `GEMINI_API_KEY`: Gemini key (optional fallback).
- `USE_OLLAMA_FIRST`: `true` means prefer Ollama first and disable Gemini unless switched off.
- `FAST_MODE`: `true` for speed-oriented processing.
- `FAST_MODE_BANGLA`: faster minimal preprocessing for Bangla-heavy pages.
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`.
- `DISABLE_MP`: set `true` to disable multiprocessing.
- `USE_GPU`: set `true` for OCR engine GPU paths where supported.

## 7) Corpus Output
Outputs are written under `last_try_output`:
- `last_try_output/output_jsons/<doc_id>/page_N.json`
- `last_try_output/merged_outputs/<doc_id>.json`
- `last_try_output/corpus/corpus.parquet` (preferred)
- `last_try_output/corpus/corpus.jsonl` (fallback when parquet deps unavailable)
- `last_try_output/corpus/corpus_stats.json`

The Parquet corpus is additive and does not replace existing JSON output.

## 8) Mac M4 Setup (MPS + Ollama)
Install Paddle for Apple Silicon:
```bash
pip install paddlepaddle
```

Enable MPS device:
```bash
export PADDLE_DEVICE=mps
```

Install and run Ollama with MiniCPM-V:
```bash
ollama pull minicpm-v:8b
ollama serve
```

Use `.env`:
```bash
USE_OLLAMA_FIRST=true
```

## 9) File Structure
```text
last_try_OCR/
├── app.py
├── main.py
├── pipeline.py
├── ocr_engine.py
├── bangla_corrector.py
├── json_builder.py
├── models.py
├── config.py
├── streamlit_ui.py
├── static/
│   └── index.html
├── bangla_wordlist.txt
├── requirements.txt
└── .env.example
```
