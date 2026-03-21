# Last-Try OCR

Government-grade hybrid OCR for Bangla + English PDFs.

## Quick Start

```bash
git clone <your-repo-url>
cd last_try_OCR
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
pip install torch torchvision
cp .env.example .env
# edit .env and set GEMINI_API_KEY if cloud fallback is needed
ollama pull qwen2.5vl:7b
ollama serve &
make run
```

Open:
- http://localhost:8000

## Python 3.14 Compatibility Note

Python 3.14 is supported for the web server and pipeline orchestration.

EasyOCR depends on PyTorch, and Python 3.14 wheels may be unavailable for some environments.
If installation fails, use Python 3.11:

```bash
pyenv install 3.11.9
pyenv local 3.11.9
```

The system architecture and behavior are identical across both versions.

## Architecture

- Local OCR: EasyOCR (Bangla + English)
- Local LLM fallback: Ollama (qwen2.5vl:7b)
- Optional cloud fallback: Gemini free tier (gemini-2.0-flash)

## Project Layout

```text
last_try_OCR/
├── __init__.py
├── config.py
├── models.py
├── exceptions.py
├── pipeline.py
├── main.py
├── core/
│   ├── pdf_router.py
│   └── ocr_engine.py
├── nlp/
│   ├── unicode_validator.py
│   ├── bangla_corrector.py
│   ├── numeric_validator.py
│   └── confidence_scorer.py
├── extraction/
│   ├── table_handler.py
│   └── image_processor.py
├── fallback/
│   └── llm_fallback.py
├── output/
│   └── json_builder.py
├── server/
│   └── app.py
├── assets/
│   ├── bangla_wordlist.txt
│   └── prompts/
│       ├── ocr_prompt.txt
│       └── ollama_prompt.txt
├── tests/
├── pyproject.toml
├── Makefile
├── Dockerfile
└── .env.example
```

## Run Modes

### API server

```bash
make run
```

### CLI

```bash
python -m last_try_OCR.main /absolute/path/file.pdf
```

## Test

```bash
make test
```

## Notes

- This repo is tuned for Mac Mini M4 with 16 GB RAM.
- Worker concurrency is intentionally capped for stability.
- Cached results are stored under merged outputs using file-hash keys.
