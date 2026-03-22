BanglaDOC Surya Clean
=====================

This folder is a fresh, cleaner implementation inspired by last_try_OCR.

Highlights
- Surya-first OCR methodology for Bangla scanned pages.
- Fallback chain: Ollama -> Gemini -> EasyOCR.
- Same web UI retained from previous project static page.
- Smaller debuggable pipeline divided into focused helper methods.

Quick start
- Follow cmd.txt for first-time setup and daily run commands.

Project layout
--------------

Repository root (`bangladoc_surya_clean/`)

| File / folder | Role |
|---------------|------|
| `.gitignore` | Ignores venv, caches, secrets, and generated `data/` outputs. |
| `README.md` | This project overview and layout. |
| `cmd.txt` | Step-by-step commands for setup, Docker, and running the server or CLI. |
| `docker-compose.yml` | Container orchestration for local runs (see cmd.txt). |
| `backend/` | Python package, HTTP server, and OCR pipeline code. |

Optional runtime directory (usually gitignored): `data/` — merged JSON, per-page JSON, and plain-text exports when `DATA_DIR` points here (see `backend/.env.example`).

### `backend/`

| File | Role |
|------|------|
| `pyproject.toml` | Package metadata, dependencies, and editable install (`pip install -e "./backend[dev]"`). |
| `.env.example` | Template for API keys, model toggles, and paths; copy to `.env` (not committed). |

### `backend/bangladoc_ocr/` (main package)

| File | Role |
|------|------|
| `__init__.py` | Package marker. |
| `cli.py` | Command-line entry for running the pipeline outside the web server. |
| `config.py` | Loads settings from environment / `.env`. |
| `exceptions.py` | Shared exception types for OCR and pipeline errors. |
| `models.py` | Data structures for pages, results, and pipeline state. |
| `pipeline.py` | High-level orchestration of document → page → OCR steps. |

### `backend/bangladoc_ocr/assets/`

| File | Role |
|------|------|
| `bangla_wordlist.txt` | Word list used by Bangla NLP / correction. |
| `prompts/ocr_prompt.txt` | Prompt text for OCR-related LLM steps. |
| `prompts/ollama_prompt.txt` | Prompt text for Ollama-based fallback. |

### `backend/bangladoc_ocr/core/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `image_describer.py` | Image description / vision helper used in the chain. |
| `ocr_engine.py` | Abstraction and wiring for OCR backends. |
| `pdf_router.py` | Decides how PDFs are split or routed (pages vs. images). |
| `surya_engine.py` | Surya model integration and inference. |

### `backend/bangladoc_ocr/extraction/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `table_handler.py` | Detects or structures tabular content from OCR output. |

### `backend/bangladoc_ocr/fallback/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `llm_fallback.py` | Coordinates LLM-based fallback when primary OCR is weak. |

### `backend/bangladoc_ocr/fallback/llm_tasks/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `gemini.py` | Google Gemini API calls for fallback text. |
| `ollama.py` | Local Ollama calls for fallback text. |
| `parser.py` | Parses LLM responses into structured pipeline data. |
| `prompts.py` | Builds or loads prompt strings for LLM tasks. |
| `state.py` | Holds mutable state across fallback steps. |

### `backend/bangladoc_ocr/nlp/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `bangla_corrector.py` | Bangla-specific spelling / word fixes using the wordlist. |
| `confidence_scorer.py` | Scores OCR confidence to trigger fallback or correction. |
| `numeric_validator.py` | Validates digits and numeric patterns in extracted text. |
| `unicode_validator.py` | Validates Bangla / Unicode ranges and normalization. |

### `backend/bangladoc_ocr/output/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `json_builder.py` | Builds merged JSON and related serialized outputs. |

### `backend/bangladoc_ocr/pipeline_tasks/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `document_processor.py` | Splits and prepares whole documents for per-page work. |
| `helpers.py` | Shared utilities for the pipeline tasks. |
| `image_tasks.py` | Image loading, preprocessing, and conversion helpers. |
| `ocr_chain.py` | Runs Surya → fallback chain for a single image or page. |
| `page_processor.py` | Per-page pipeline: OCR, NLP, and output assembly. |

### `backend/bangladoc_ocr/server/`

| File | Role |
|------|------|
| `__init__.py` | Subpackage marker. |
| `app.py` | FastAPI (or similar) app: upload routes, static UI, and pipeline hooks. |

### `backend/bangladoc_ocr/static/`

| File | Role |
|------|------|
| `index.html` | Web UI for uploading documents and viewing OCR results. |

### `backend/bangladoc_ocr/tests/`

| File | Role |
|------|------|
| `__init__.py` | Test package marker. |
| `test_bangla_corrector.py` | Unit tests for `nlp/bangla_corrector.py`. |
| `test_confidence_scorer.py` | Unit tests for `nlp/confidence_scorer.py`. |
| `test_numeric_validator.py` | Unit tests for `nlp/numeric_validator.py`. |
| `test_unicode_validator.py` | Unit tests for `nlp/unicode_validator.py`. |

### Generated / local-only (not layout documentation)

- `backend/venv/` — Python virtual environment (create per `cmd.txt`).
- `**/__pycache__/` — Bytecode; safe to delete.
- `backend/bangladoc.egg-info/` — Produced by `pip install -e`.
- `backend/.env` — Your secrets; copy from `.env.example`.
