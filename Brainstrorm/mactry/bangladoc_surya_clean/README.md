BanglaDOC Surya Clean
=====================

Production-oriented OCR pipeline for Bangla-heavy PDFs with deterministic local OCR, confidence-aware LLM fallback, and structured corpus export.

This project is built for scanned and mixed PDFs where script quality varies across pages. It prioritizes correctness, traceability, and debuggable pipeline stages over hidden "magic" behavior.

## Core Capabilities

- Surya-first OCR path for scanned Bangla pages.
- Confidence-aware gating to skip expensive LLM fallback when local OCR is already good.
- Fallback chain: Ollama -> Gemini -> EasyOCR.
- Page-level table extraction for both digital and scanned pages.
- Engine-tagged output artifacts (`_surya`, `_ollama`, `_gemini`, `_easyocr`, `_digital`, `_mixed`).
- Corpus export (`parquet` with JSONL fallback) plus aggregated corpus stats.
- FastAPI server, browser UI, and CLI entrypoint using the same core pipeline.

---

## Getting Started (Teammate Onboarding)

### ⚡ Quick Start - Docker (Recommended for Any OS)

Docker is **the easiest way** to get running on any OS (Windows, Linux, Mac). No Python/Ollama setup needed—everything is containerized.

#### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (Windows/Mac) or [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
- 8+ GB RAM, 20+ GB disk space

#### One-Command Setup

```bash
# Clone or navigate to project
cd bangladoc_surya_clean

# Build Docker image (one time, includes all dependencies)
docker-compose build

# Start all services
docker-compose up -d

# Check services are healthy
docker ps  # should show postgres

# Open UI in browser
open http://localhost:8000
# or on Windows: start http://localhost:8000

# Stop all services when done
docker-compose down
```

#### Verify Docker Setup Works

```bash
# Check API health
curl http://localhost:8000/health

# Run a test OCR job (copy a PDF to test_input/ first)
curl -X POST http://localhost:8000/ocr \
  -F "files=@test_input/sample.pdf"
```

---

### 🔧 Native Setup (Windows/Linux/Mac)

If you prefer to manage your environment directly:

#### System Prerequisites

**Windows 10/11:**
- [Python 3.12+](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- [Git Bash](https://git-scm.com/download/win) or PowerShell
- [PostgreSQL 15+](https://www.postgresql.org/download/windows/) or use Docker for DB only
- [Ollama](https://ollama.ai/download) (optional, for local vision models)

**Linux (Ubuntu 22.04+):**
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.12 python3-pip python3-venv \
  postgresql postgresql-contrib git wget curl

# Install Ollama (optional)
curl https://ollama.ai/install.sh | sh
```

**macOS (Intel/Apple Silicon):**
```bash
# Using Homebrew
brew install python@3.12 postgresql git
brew install ollama  # optional

# For Apple Silicon, set fallback
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

#### Installation Steps

**1. Clone and navigate**
```bash
git clone <repo-url>
cd bangladoc_surya_clean
```

**2. Copy environment file**
```bash
cp backend/.env.example backend/.env
```

**3. Edit `.env` for your system**
```bash
# backend/.env

# OCR flow control
SURYA_ENABLED=true           # Set to false on low-RAM systems
OLLAMA_ENABLED=true
GEMINI_ENABLED=false         # Set true if you have API key

# Database (local PostgreSQL or Docker container)
DATABASE_URL=postgresql://bangladoc:arka@localhost:5432/bangladoc
REDIS_URL=redis://localhost:6379/0

# Output directory
DATA_DIR=../data

# Optional: point to remote Ollama
# OLLAMA_BASE_URL=http://192.168.1.xxx:11434
```

**4. Create Python virtual environment**
```bash
# Windows (PowerShell)
python -m venv backend/venv
backend/venv/Scripts/Activate.ps1

# Linux/Mac
python3 -m venv backend/venv
source backend/venv/bin/activate
```

**5. Install dependencies**
```bash
# Upgrade pip first
python -m pip install --upgrade pip setuptools wheel

# Install backend (including all extras)
python -m pip install -e "./backend[dev]"

# Verify Surya models are available
python -c "from surya.recognition import RecognitionPredictor; print('✓ Surya OK')"
```

**6. Start PostgreSQL**

**Windows (PostgreSQL installed):**
```bash
# PostgreSQL service should start automatically
# Or in Services menu: PostgreSQL 15
```

**Linux:**
```bash
sudo systemctl start postgresql
sudo systemctl status postgresql
```

**macOS:**
```bash
brew services start postgresql
brew services status
```

**Or use Docker for database only:**
```bash
docker run -d \
  --name bangladoc-db \
  -e POSTGRES_USER=bangladoc \
  -e POSTGRES_PASSWORD=arka \
  -e POSTGRES_DB=bangladoc \
  -p 5432:5432 \
  postgres:15
```

**7. Pull Ollama models (optional but recommended)**
```bash
ollama pull qwen2.5vl:7b      # Vision model
ollama pull moondream2         # Image description
```

**8. Start services**

Terminal 1 - FastAPI:
```bash
cd backend
source venv/bin/activate      # or .../Scripts/Activate.ps1 on Windows
uvicorn bangladoc_ocr.server.app:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 - Celery Worker:
```bash
cd backend
source venv/bin/activate
python -m celery -A bangladoc_ocr.celery_app:celery_app worker \
  --loglevel=info --pool=solo -n worker1@%h
```

Terminal 3 - Ollama (if using):
```bash
ollama serve
```

**9. Open UI**
```bash
# Browser
open http://localhost:8000
```

**10. Test OCR**
```bash
# CLI test
source backend/venv/bin/activate
bangladoc /path/to/test.pdf --verbose
```

---

### 📊 Comparison: Docker vs Native

| Aspect | Docker | Native |
|--------|--------|--------|
| **Setup Time** | 5 min | 20-30 min |
| **OS Support** | Windows/Linux/Mac | Each OS different |
| **Dependencies** | Isolated | System-wide |
| **Performance** | Slight overhead | Native speed |
| **Debugging** | Container logs | Direct access |
| **Modifications** | Rebuild image | Edit code directly |
| **Team Consistency** | ✅ Guaranteed identical | ❌ OS variations |
| **Recommended** | ✅ First choice | For dev customization |

---

### 🐛 Troubleshooting Teammate Setup

#### "Port 8000 already in use"
```bash
# Find and kill process using port 8000
# Windows (PowerShell)
Get-Process | Where-Object {$_.Handles -like "*8000*"}
Stop-Process -Id <PID> -Force

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

#### "PostgreSQL connection refused"
```bash
# Check if DB is running
# Windows: Services app → PostgreSQL 15 → start
# Linux: sudo systemctl start postgresql
# Mac: brew services start postgresql
# Or use Docker: docker start bangladoc-db
```

#### "Surya models not found"
```bash
# Re-download models
python -m pip install --upgrade surya-ocr
python -c "from surya.foundation import FoundationPredictor; f=FoundationPredictor.from_pretrained('surya')"
```

#### "Ollama connection timeout"
```bash
# Make sure Ollama is running
ollama serve

# Check if accessible
curl http://localhost:11434/api/tags
```

#### "Event loop is closed" / "Task attached to different loop" (Celery)
- Already fixed in updated code! Just ensure you're using latest tasks.py
- If still issues: `pkill -f "celery -A" && restart worker`

---

## End-to-End Flow

### 1) Entry points

- HTTP: `backend/bangladoc_ocr/server/app.py`
  - `POST /ocr` accepts PDF uploads and triggers processing.
  - `GET /ocr/progress` returns progress state.
  - `GET /corpus/stats` and `GET /corpus/export` expose corpus outputs.
  - `POST /corpus/verify` toggles page verification flags and rebuilds corpus stats.
- CLI: `backend/bangladoc_ocr/cli.py`
  - Runs the same document pipeline for one or more PDF files.

### 2) Document orchestration

`process_pdf()` in `backend/bangladoc_ocr/pipeline_tasks/document_processor.py`:

1. Reloads runtime config from `.env`.
2. Optionally warms Surya (when enabled).
3. Opens the PDF and iterates pages.
4. Calls `process_page()` for each page.
5. Builds final `DocumentResult` metadata.
6. Persists per-page JSON, merged JSON, TXT, and corpus rows.

### 3) Per-page processing

`process_page()` in `backend/bangladoc_ocr/pipeline_tasks/page_processor.py`:

1. Detects page type (`digital` or `scanned`).
2. Digital page path:
   - Extract text via PyMuPDF.
   - Validate Unicode/script consistency.
   - Apply numeric normalization.
   - Build content blocks and digital tables.
3. Scanned page path:
   - Render page to image.
   - Run scanned OCR chain (`run_scanned_ocr`).
   - Convert OCR blocks to detection tuples and extract scanned tables.
4. Extract embedded page images and generate short descriptions.
5. Compute confidence score and finalize page decisions.

### 4) Scanned OCR chain

`run_scanned_ocr()` in `backend/bangladoc_ocr/pipeline_tasks/ocr_chain.py`:

1. Try Surya first (if enabled and available).
2. If Surya does not produce a valid result:
   - Run fast EasyOCR quick pass.
   - Score confidence and decide `needs_api_fallback(...)`.
   - If local quality is sufficient, skip LLM and return EasyOCR output.
3. If fallback is needed:
   - Try Ollama first.
   - If Ollama fails, try Gemini.
4. If all LLM fallback fails:
   - Run full EasyOCR fallback as final local safety net.

### 5) NLP correction and scoring

- `bangla_corrector.py` applies Bangla-aware cleanup and correction.
- `unicode_validator.py` handles script hygiene and suspicious line stripping.
- `confidence_scorer.py` computes language-aware confidence and fallback thresholds.

### 6) Output writing

`backend/bangladoc_ocr/output/json_builder.py`:

- Ensures output directories exist.
- Writes per-page JSON files with engine suffix.
- Writes merged document JSON with `document.output_engine_tag`.
- Writes extracted TXT with engine suffix.
- Appends corpus rows and updates corpus stats.

## Project Structure Diagram

```text
bangladoc_surya_clean/
├── README.md
├── cmd.txt
├── docker-compose.yml
├── data/                              # runtime outputs (gitignored in normal flow)
│   ├── output_images/
│   ├── output_jsons/
│   ├── merged_outputs/
│   ├── output_texts/
│   └── corpus/
└── backend/
    ├── .env
    ├── .env.example
    ├── pyproject.toml
    └── bangladoc_ocr/
        ├── __init__.py
        ├── cli.py
        ├── config.py
        ├── exceptions.py
        ├── models.py
        ├── pipeline.py
        ├── assets/
        │   ├── bangla_wordlist.txt
        │   └── prompts/
        │       ├── ocr_prompt.txt
        │       └── ollama_prompt.txt
        ├── core/
        │   ├── pdf_router.py
        │   ├── ocr_engine.py
        │   ├── surya_engine.py
        │   └── image_describer.py
        ├── pipeline_tasks/
        │   ├── document_processor.py
        │   ├── page_processor.py
        │   ├── ocr_chain.py
        │   ├── helpers.py
        │   └── image_tasks.py
        ├── extraction/
        │   └── table_handler.py
        ├── nlp/
        │   ├── bangla_corrector.py
        │   ├── confidence_scorer.py
        │   ├── numeric_validator.py
        │   └── unicode_validator.py
        ├── fallback/
        │   ├── llm_fallback.py
        │   └── llm_tasks/
        │       ├── gemini.py
        │       ├── ollama.py
        │       ├── parser.py
        │       ├── prompts.py
        │       └── state.py
        ├── output/
        │   └── json_builder.py
        ├── server/
        │   └── app.py
        ├── static/
        │   └── index.html
        └── tests/
            ├── test_bangla_corrector.py
            ├── test_confidence_scorer.py
            ├── test_numeric_validator.py
            └── test_unicode_validator.py
```

## Pipeline Methodology

### OCR decision strategy

- Use local OCR whenever quality is adequate.
- Use LLM fallback only when confidence thresholds indicate it is necessary.
- Keep a strict chain order so behavior remains deterministic and explainable.

### Script robustness strategy

- Detect and remove Devanagari-dominant contaminated lines from Surya output.
- Reject Surya output only after cleanup if still script-mismatched or too short.

### Output traceability strategy

- Every output is tagged by final extraction engine.
- Mixed-engine multi-page documents are explicitly marked `_mixed`.
- Page decisions are captured in logs/decision arrays for debugging.

## Full Process Diagram (Step-by-step)

```mermaid
flowchart TD
    A[Input PDF - API or CLI] --> B[document_processor.process_pdf]
    B --> C[config.refresh_config]
    C --> D[Open PDF with pdf_router.open_pdf]
    D --> E{For each page}
    E --> F[page_processor.process_page]
    F --> G{detect_page_type}

    G -->|digital| H[extract_digital_text]
    H --> I[validate_digital_text]
    I -->|valid| J[validate_and_fix_numbers]
    J --> K[helpers.text_to_blocks]
    K --> L[extract_tables_digital]
    I -->|invalid| M[reroute to scanned path]

    G -->|scanned| N[render_page_to_image]
    M --> N
    N --> O[ocr_chain.run_scanned_ocr]
    O --> P{SURYA enabled + available}
    P -->|yes| Q[surya_engine.ocr_bytes]
    P -->|no| R[Quick EasyOCR pass]
    Q --> S{usable Surya text?}
    S -->|yes| T[helpers.text_to_blocks + apply_corrections]
    S -->|no| R
    R --> U[score_blocks]
    U --> V{needs_api_fallback?}
    V -->|no| W[Use EasyOCR local result]
    V -->|yes| X[llm_fallback: Ollama]
    X -->|fail| Y[llm_fallback: Gemini]
    Y -->|fail| Z[Full EasyOCR fallback]

    T --> AA[scanned table extraction]
    W --> AA
    X --> AA
    Y --> AA
    Z --> AA

    AA --> AB[extract_page_images]
    AB --> AC[image_tasks.describe_embedded_images]
    AC --> AD[confidence_scorer.score_blocks]
    AD --> AE[Build PageResult]
    AE --> AF{more pages?}
    AF -->|yes| E
    AF -->|no| AG[Build DocumentResult]
    AG --> AH[json_builder.save_document_json]
    AH --> AI[page JSON + merged JSON + TXT + corpus]
```

## NLP and Correction Pipeline Diagram

```mermaid
flowchart LR
    A[Raw OCR blocks/text] --> B[helpers.apply_corrections]
    B --> C[bangla_corrector.correct_bangla_text]
    C --> D[unicode_validator.strip_devanagari_dominant_lines]
    D --> E[Updated blocks]
    E --> F[numeric_validator.validate_and_fix_numbers - digital path]
    F --> G[Cleaned page text]
```

### What each NLP module does

- `bangla_corrector.py`: applies Bangla-aware text cleanup and correction (word validity, common OCR artifacts, script-sensitive fixes).
- `unicode_validator.py`: measures Bangla/script ratios, strips Devanagari-dominant noise lines, and removes non-printable/control artifacts in output serialization.
- `numeric_validator.py`: repairs OCR-number confusions and validates numeric consistency (digital path).
- `confidence_scorer.py`: computes weighted confidence and decides if API fallback is needed.

## Confidence Scoring Diagram

```mermaid
flowchart TD
    A[Page content blocks] --> B[avg OCR confidence]
    A --> C[Unicode/Bangla ratio]
    A --> D[Dictionary validity score]
    A --> E[Invalid glyph penalty]
    A --> F[Numeric consistency score]
    A --> G[Structural consistency score]

    B --> H[Weighted sum]
    C --> H
    D --> H
    E --> H
    F --> H
    G --> H

    H --> I[Final confidence 0.0 to 1.0]
    I --> J{needs_api_fallback?}
    J -->|below threshold| K[LLM fallback required]
    J -->|above threshold| L[Keep local OCR result]
```

### How score is valued

- The scorer uses different weight profiles for Bangla-heavy vs English-heavy pages.
- Threshold decision:
  - Bangla-heavy uses `API_FALLBACK_THRESHOLD_BANGLA`.
  - Non-Bangla-heavy uses `API_FALLBACK_THRESHOLD_ENGLISH`.
- If confidence is below threshold, API fallback is attempted; otherwise local OCR is accepted.

---

## Detailed Step-by-Step Processing Diagrams

### Diagram 1: End-to-End Processing Pipeline (Input → Output)

```mermaid
flowchart TD
    A["📄 PDF Input<br/>API or CLI"] --> B["1️⃣ Initialize<br/>Reload config, warm Surya"]
    B --> C["2️⃣ Open PDF<br/>Get page count"]
    C --> D["3️⃣ Page Loop<br/>For each page"]
    D --> E{4️⃣ Page Type<br/>Detection}
    
    E -->|Digital<br/>≥30 chars| F["5a️⃣ DIGITAL PATH<br/>PyMuPDF extract"]
    E -->|Scanned<br/>&lt;30 or no text| G["5b️⃣ SCANNED PATH<br/>OCR Chain"]
    
    F --> F1["Extract & validate"]
    F1 --> F2{Valid?}
    F2 -->|NO| G
    F2 -->|YES| F3["Numeric normalization"]
    F3 --> F4["Extract tables pdfplumber"]
    
    G --> G1["Render page to PNG"]
    G1 --> G2["run_scanned_ocr:<br/>Surya → Quick EasyOCR<br/>→ LLM chain → Full EasyOCR"]
    
    F4 --> H["6️⃣ PageResult Created<br/>engine tag assigned"]
    G2 --> H
    
    H --> I["7️⃣ Text Corrections<br/>Strip control/CID/Devanagari"]
    I --> J["8️⃣ Confidence Scoring<br/>6-signal language-aware"]
    
    J --> K["9️⃣ Extract Images<br/>Describe with Ollama/Gemini"]
    K --> L["🔟 Extract Tables<br/>Digital/scanned mode"]
    L --> M["1️⃣1️⃣ Build DocumentResult<br/>on last page"]
    
    M --> N["1️⃣2️⃣ Save Outputs<br/>per-page JSON"]
    N --> O["1️⃣3️⃣ Merged JSON<br/>1️⃣4️⃣ TXT Export"]
    O --> P["1️⃣5️⃣ Update Corpus<br/>Parquet + stats"]
    P --> Q["✅ COMPLETE"]
    
    style A fill:#e1f5ff
    style Q fill:#c8e6c9
```

### Diagram 2: Page Type Detection & Routing

```mermaid
flowchart TD
    A["Page loaded<br/>from PDF"] --> B["Step 1:<br/>Extract text<br/>with PyMuPDF"]
    B --> C{Step 2:<br/>Check length<br/>≥ 30 chars?}
    
    C -->|YES| D["✓ DIGITAL PAGE"]
    C -->|NO/EMPTY| E["✓ SCANNED PAGE"]
    
    D --> D1["Step 3a: Extract PyMuPDF text"]
    D1 --> D2["Step 3b: Validate Unicode<br/>Check control chars/CID refs"]
    D2 --> D3{Step 3c: Valid?}
    D3 -->|YES| D4["Step 3d: Normalize numbers<br/>Step 3e: Extract with pdfplumber"]
    D3 -->|INVALID| E
    D4 --> R1["PageResult<br/>method: digital"]
    
    E --> E1["Step 4: Render page<br/>at configured DPI"]
    E1 --> E2["Step 5: run_scanned_ocr"]
    E2 --> R2["PageResult<br/>method: scanned"]
    
    R1 --> X["Return PageResult"]
    R2 --> X
    
    style D fill:#fff9c4
    style E fill:#ffe0b2
    style X fill:#c8e6c9
```

### Diagram 3: Scanned OCR Chain - Complete Fallback Sequence

```mermaid
flowchart TD
    A["Scanned page<br/>PNG image"] --> B{Step 1:<br/>SURYA_ENABLED?}
    
    B -->|NO| C["Step 2: Skip Surya"]
    B -->|YES| B1["Step 2a: Check<br/>models available?"]
    B1 -->|NO| C
    B1 -->|YES| B2["Step 2b: surya_ocr<br/>with Devanagari filter"]
    
    B2 --> B3{Step 3:<br/>Valid result?<br/>≥20 chars<br/>+ script match}
    B3 -->|YES| R1["✓ RETURN SURYA"]
    B3 -->|NO| C
    
    C --> Q["Step 4: Quick EasyOCR<br/>fast_mode=True"]
    Q --> Q1["Step 5: Score confidence<br/>6 signals"]
    Q1 --> Q2{Step 6:<br/>API fallback<br/>needed?<br/>conf ≤ threshold}
    
    Q2 -->|NO| R2["✓ RETURN EASYOCR<br/>confidence sufficient"]
    Q2 -->|YES| L["Step 7: Enter LLM chain"]
    
    L --> L1{Step 8a:<br/>Ollama available?}
    L1 -->|NO| L2["Step 8b: Skip Ollama"]
    L1 -->|YES| L1A["Step 8c: Image sizing<br/>896-1280px"]
    L1A --> L1B["Step 8d: Try Ollama<br/>qwen2.5vl, minicpm,<br/>llava, moondream"]
    L1B --> L1C{Success?}
    L1C -->|YES| R3["✓ RETURN OLLAMA"]
    L1C -->|NO| L2
    
    L2 --> L3{Step 9a:<br/>Gemini enabled<br/>+ API key?}
    L3 -->|NO| F
    L3 -->|YES| L3A["Step 9b: Image ≤1024px"]
    L3A --> L3B["Step 9c: Try Gemini 2.0<br/>2 retries, 2s delay"]
    L3B --> L3C{Success?}
    L3C -->|YES| R4["✓ RETURN GEMINI"]
    L3C -->|NO| F
    
    F["Step 10: Full EasyOCR<br/>fast_mode=False<br/>guaranteed success"]
    F --> R5["✓ RETURN EASYOCR"]
    
    R1 --> X["Step 11: Apply<br/>text corrections"]
    R2 --> X
    R3 --> X
    R4 --> X
    R5 --> X
    
    X --> X1["Step 12a: Strip control/CID"]
    X1 --> X2["Step 12b: Numeric validation<br/>O→0, I→1"]
    X2 --> X3["Step 12c: Unicode validation<br/>Bangla ratio, strip Devanagari"]
    X3 --> Y["Step 13: Build PageResult<br/>with engine tag"]
    
    style R1 fill:#b3e5fc
    style R2 fill:#b3e5fc
    style R3 fill:#90caf9
    style R4 fill:#81c784
    style R5 fill:#ffd54f
    style Y fill:#c8e6c9
```

### Diagram 4: Confidence Scoring (6-Signal System)

```mermaid
flowchart TD
    A["Page blocks<br/>text + bounds"] --> B["Signal 1️⃣<br/>OCR Base Confidence"]
    B --> B1["Average conf<br/>from all blocks"]
    
    A --> C["Signal 2️⃣<br/>Character Quality"]
    C --> C1["Bangla % ratio<br/>Devanagari %<br/>Invalid chars"]
    
    A --> D["Signal 3️⃣<br/>Dictionary Match"]
    D --> D1["Valid Bangla words<br/>/ total words"]
    
    A --> E["Signal 4️⃣<br/>Control Char Penalty"]
    E --> E1["Count: U+200B<br/>U+FEFF, special<br/>Unicode chars"]
    
    A --> F["Signal 5️⃣<br/>Numeric Consistency"]
    F --> F1["O→0, I→1<br/>patterns valid?"]
    
    A --> G["Signal 6️⃣<br/>Structural Consistency"]
    G --> G1["Single-char ratio<br/>abnormal?"]
    
    B1 --> H["Weighted Sum<br/>confidence = 0.0-1.0"]
    C1 --> H
    D1 --> H
    E1 --> H
    F1 --> H
    G1 --> H
    
    H --> I{is_bangla?}
    I -->|YES| J{conf &lt; 0.86<br/>+ valid text?}
    I -->|NO| K["Use calculated"]
    J -->|YES| L["FLOOR: conf=0.86<br/>Bangla page boost"]
    J -->|NO| K
    
    L --> M["Final Confidence"]
    K --> M
    
    M --> T{Tier Assignment}
    T -->|conf ≥ 0.85| O["🥇 GOLD<br/>High confidence"]
    T -->|0.65-0.84| R["🥈 SILVER<br/>Medium"]
    T -->|conf &lt; 0.65| Q["🥉 BRONZE<br/>Low confidence"]
    
    O --> X["Store in corpus<br/>with tier"]
    R --> X
    Q --> X
    
    style H fill:#fff9c4
    style M fill:#b3e5fc
    style O fill:#81c784
    style R fill:#ffc107
    style Q fill:#ff7043
```

### Diagram 5: HTTP API Request → Job Completion

```mermaid
flowchart TD
    A["Client: POST /ocr<br/>multipart form"] --> B["Server: Authenticate<br/>user session"]
    B --> C["Save PDF to disk<br/>UPLOAD_DIR/uuid"]
    
    C --> D["Step 1: Create Document<br/>status=PENDING<br/>total_pages=unknown"]
    D --> E["Step 2: Get page count<br/>from PDF"]
    E --> F["Step 3: Create OCRJob<br/>status=PENDING<br/>celery_task_id=uuid"]
    
    F --> G["Step 4: Dispatch Celery<br/>task to Redis"]
    G --> H["Step 5: Return 202<br/>job_id, celery_task_id"]
    
    H --> I["Client polling loop"]
    I --> J["Step 6: GET /jobs/{job_id}"]
    J --> K["Step 7: Query DB<br/>job.status, doc.status"]
    K --> L["Step 8: Read progress JSON<br/>current_page, total_pages"]
    L --> M["Return {status,<br/>progress_percent}"]
    
    M --> N{Complete?}
    N -->|NO| I
    N -->|YES| O["Step 9: GET /documents/{doc_id}"]
    O --> P["Step 10: Query Page records<br/>all pages with engine,<br/>confidence, text"]
    P --> Q["Return {pages: [...]<br/>metadata}"]
    Q --> R["Display results<br/>to user"]
    
    style A fill:#e1f5ff
    style H fill:#fff9c4
    style Q fill:#c8e6c9
    style R fill:#c8e6c9
```

### Diagram 6: Celery Worker Async Task Execution

```mermaid
flowchart TD
    A["Worker receives task<br/>from Redis queue"] --> B["Step 1: Get persistent<br/>event loop<br/>_get_worker_loop"]
    B --> C["Step 2: asyncio.set<br/>_event_loop(loop)"]
    C --> D["Step 3: loop.run<br/>_until_complete"]
    
    D --> E["Step 4: async context<br/>AsyncSessionLocal()"]
    E --> E1["Step 5: Load OCRJob<br/>from DB - check exists"]
    E1 --> E2["Step 6: Load Document<br/>from DB"]
    E2 --> E3["Step 7: Update status<br/>job=PROCESSING<br/>doc=PROCESSING"]
    E3 --> E4["Step 8: db.commit"]
    
    E4 --> F["Step 9: Write progress JSON<br/>{doc_id, page=0,<br/>total=?, status}"]
    E4 --> G["Step 10: asyncio.to_thread<br/>process_pdf<br/>blocking sync call"]
    
    G --> G1["THREAD CONTEXT:<br/>For each page n"]
    G1 --> G2["Step 11: process_page(n)"]
    G2 --> G3["Step 12: progress_callback(n)"]
    G3 --> G3A["asyncio.run_coroutine<br/>_threadsafe"]
    G3A --> G3B["async _update_progress<br/>update doc.total_pages<br/>write JSON"]
    
    G1 --> G4["Build PageResult"]
    G4 --> G5["Return DocumentResult"]
    
    G5 --> H["Back in async context"]
    H --> I["Step 13: db.execute<br/>delete old Pages"]
    I --> J["Step 14: For each page<br/>db.add(Page(...engine,<br/>confidence, text))"]
    J --> K["Step 15: Update doc<br/>status=DONE"]
    K --> L["Step 16: Update job<br/>status=DONE"]
    L --> M["Step 17: db.commit"]
    
    M --> N["Step 18: JSON builder<br/>save all outputs"]
    N --> N1["per-page JSON"]
    N --> N2["merged JSON"]
    N --> N3["TXT file"]
    N --> N4["corpus parquet"]
    
    N1 --> O["✅ Task complete"]
    
    E1 -.Exception.-> P["Exception caught"]
    P --> Q["Step 19: Set status<br/>doc=FAILED<br/>job=FAILED<br/>error_msg=str"]
    Q --> R["Step 20: Write progress<br/>status=failed"]
    R --> S["Step 21: db.commit"]
    S --> T["❌ Task failed"]
    
    style A fill:#e1f5ff
    style O fill:#c8e6c9
    style T fill:#ff7043
```

### Diagram 7: Database Schema & OCR Job Lifecycle

```mermaid
graph TD
    U["👤 User"]
    
    U -->|1:N| D["📋 Document<br/>├─ id<br/>├─ doc_id hash<br/>├─ user_id<br/>├─ status<br/>├─ total_pages<br/>└─ domain"]
    
    D -->|1:N| J["⚙️ OCRJob<br/>├─ id<br/>├─ document_id<br/>├─ celery_task_id<br/>├─ status<br/>├─ error_msg<br/>├─ started_at<br/>└─ completed_at"]
    
    D -->|1:N| P["📄 Page<br/>├─ id<br/>├─ document_id<br/>├─ page_number<br/>├─ engine<br/>├─ confidence_score<br/>├─ full_text<br/>└─ verified"]
    
    P -->|1:N| C["🔤 Chunk<br/>├─ id<br/>├─ page_id<br/>├─ text<br/>├─ qdrant_point_id<br/>└─ embedding"]
    
    J -->|tracks| D
    
    subgraph Status Lifecycle
        direction LR
        S1["❌ PENDING"]
        S2["⏳ PROCESSING"]
        S3["✅ DONE"]
        S4["❌ FAILED"]
        S1 -->|dispatch task| S2
        S2 -->|success| S3
        S2 -->|error| S4
        S1 -.cancel.-> S4
    end
    
    style U fill:#c5cae9
    style D fill:#e1f5ff
    style J fill:#fff9c4
    style P fill:#c8e6c9
    style C fill:#f0f4c3
```

### Diagram 8: CLI vs API Entry Points (Same Core Pipeline)

```mermaid
flowchart TD
    subgraph CLI["🖥️ CLI Path"]
        A1["$ bangladoc file.pdf<br/>--verbose --domain=legal"]
        A2["Step 1: Parse CLI args"]
        A3["Step 2: Synchronous call<br/>process_pdf direct<br/>in main thread"]
        A4["Step 3: Progress callback<br/>print to stdout"]
        A5["Step 4: DocumentResult<br/>returned immediately"]
        A6["Step 5: Save outputs<br/>to data/"]
        
        A1 --> A2
        A2 --> A3
        A3 --> A4
        A4 --> A5
        A5 --> A6
    end
    
    subgraph CORE["⚙️ Shared Core Pipeline"]
        X1["process_pdf(file_path,<br/>save_outputs, domain,<br/>progress_callback)"]
        X2["Step A: Reload config"]
        X3["Step B: Warm Surya"]
        X4["Step C: For each page<br/>process_page"]
        X5["Step D: Build<br/>DocumentResult"]
        X6["Step E: Return result"]
        
        X1 --> X2
        X2 --> X3
        X3 --> X4
        X4 --> X5
        X5 --> X6
    end
    
    subgraph API["🌐 API Path"]
        B1["POST /ocr<br/>multipart PDF<br/>from browser"]
        B2["Step 1: Register<br/>Document + OCRJob<br/>in DB"]
        B3["Step 2: Dispatch async<br/>Celery task"]
        B4["Step 3: Return 202<br/>job_id"]
        B5["Step 4: Client polls<br/>GET /jobs/{id}"]
        B6["Step 5: Worker executes<br/>process_pdf in<br/>persistent async loop"]
        B7["Step 6: Progress callback<br/>updates DB + JSON"]
        B8["Step 7: job.status=DONE<br/>set on completion"]
        B9["Step 8: GET /documents/{id}<br/>fetch final results"]
        
        B1 --> B2
        B2 --> B3
        B3 --> B4
        B4 --> B5
        B5 --> B6
        B6 --> B7
        B7 --> B8
        B8 --> B9
    end
    
    A3 -.calls.-> X1
    B6 -.calls.-> X1
    
    X6 --> O["Outputs:<br/>📄 JSON<br/>📄 TXT<br/>🖼️ images<br/>📊 corpus"]
    
    style X1 fill:#fff9c4
    style O fill:#c8e6c9
```

## Architecture Pipeline Diagram

```mermaid
flowchart TB
    subgraph Entry
      A1[FastAPI server app.py]
      A2[CLI cli.py]
    end

    subgraph Orchestration
      B1[document_processor.py]
      B2[page_processor.py]
      B3[ocr_chain.py]
    end

    subgraph OCR_Engines
      C1[surya_engine.py]
      C2[ocr_engine.py EasyOCR]
      C3[fallback/llm_fallback.py]
      C4[fallback/llm_tasks/ollama.py]
      C5[fallback/llm_tasks/gemini.py]
    end

    subgraph NLP_and_Validation
      D1[bangla_corrector.py]
      D2[unicode_validator.py]
      D3[numeric_validator.py]
      D4[confidence_scorer.py]
    end

    subgraph Extraction_and_Output
      E1[extraction/table_handler.py]
      E2[pipeline_tasks/image_tasks.py]
      E3[core/image_describer.py]
      E4[output/json_builder.py]
    end

    A1 --> B1
    A2 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> C1
    B3 --> C2
    B3 --> C3
    C3 --> C4
    C3 --> C5
    B2 --> D1
    B2 --> D2
    B2 --> D3
    B2 --> D4
    B2 --> E1
    B2 --> E2
    E2 --> E3
    B1 --> E4
```

## Runtime Configuration

Configured in `backend/.env` (template: `backend/.env.example`).

Most important controls:

- `SURYA_ENABLED=true|false`
  - `true`: Surya-first scanned flow.
  - `false`: skip Surya and begin from local/LLM chain.
- `DATA_DIR=...`
  - Relative paths are resolved from project root (`bangladoc_surya_clean`).
- `GEMINI_ENABLED`, `GEMINI_API_KEY`
  - Enables Gemini fallback when Ollama fails.
- `OLLAMA_BASE_URL`, `OLLAMA_IMAGE_MODEL`
  - Controls local Ollama fallback and image description model.
- `DPI`, `MAX_WORKERS`, threshold values
  - Controls rendering/throughput/scoring behavior.

## Output Structure

Assuming `DATA_DIR=../data`, the generated artifacts are:

- `data/output_images/<doc_id>/`
  - Rendered page images and extracted embedded images.
- `data/output_jsons/<doc_id>/page_<n>_<engine>.json`
  - Page-level structured output.
- `data/merged_outputs/<doc_id>_<engine-or-mixed>.json`
  - Full document output.
- `data/output_texts/<doc_id>_<engine-or-mixed>.txt`
  - Plain text export grouped by page.
- `data/corpus/corpus.parquet` (or `corpus.jsonl` fallback)
  - Row-wise corpus data for analysis/training.
- `data/corpus/corpus_stats.json`
  - Aggregated corpus metrics (by domain/tier/engine).

## Internal Call Graph

```mermaid
flowchart TD
    A[POST /ocr or CLI] --> B[process_pdf]
    B --> C[process_page]
    C --> D{digital or scanned}
    D -->|digital| E[extract_digital_text + validate + numeric fix]
    D -->|scanned| F[run_scanned_ocr]
    F --> G[Surya]
    G -->|fail| H[Quick EasyOCR score]
    H -->|sufficient| I[use EasyOCR local]
    H -->|needs fallback| J[Ollama]
    J -->|fail| K[Gemini]
    K -->|fail| L[Full EasyOCR]
    E --> M[build PageResult]
    I --> M
    J --> M
    K --> M
    L --> M
    M --> N[save_document_json]
    N --> O[page JSON + merged JSON + TXT + corpus]
```

## Professional File Structure Guide

### Repository root

| Path | Responsibility |
|---|---|
| `.gitignore` | Ignores runtime artifacts, caches, venvs, local secrets. |
| `README.md` | This technical and operational documentation. |
| `cmd.txt` | Practical setup/run command cookbook. |
| `docker-compose.yml` | Containerized deployment/dev orchestration. |
| `backend/` | Python package, API server, OCR engines, pipeline, tests. |
| `data/` | Runtime-generated artifacts (usually ignored by git). |

### `backend/`

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, extras, entry points. |
| `.env.example` | Environment template with safe defaults. |
| `.env` | Local runtime secrets and toggles (not committed). |
| `bangladoc_ocr/` | Main OCR application package. |

### `backend/bangladoc_ocr/`

| Path | Responsibility |
|---|---|
| `__init__.py` | Package marker. |
| `cli.py` | Command-line entrypoint, shared pipeline invocation. |
| `config.py` | Environment loading, dynamic config refresh, path setup. |
| `exceptions.py` | Domain-specific exceptions for OCR and fallback errors. |
| `models.py` | Dataclasses for page/document/schema exchange between stages. |
| `pipeline.py` | Compatibility export for `process_pdf`. |

### `backend/bangladoc_ocr/core/`

| Path | Responsibility |
|---|---|
| `pdf_router.py` | PDF/page utilities: classification, rendering, extraction. |
| `ocr_engine.py` | Local OCR calls (EasyOCR), detections-to-block conversion. |
| `surya_engine.py` | Surya model lifecycle, thread-safe loading, OCR call wrapper. |
| `image_describer.py` | Async image caption fallback (Ollama then Gemini). |

### `backend/bangladoc_ocr/pipeline_tasks/`

| Path | Responsibility |
|---|---|
| `document_processor.py` | Full document loop and result aggregation. |
| `page_processor.py` | Digital/scanned branching and page-level assembly. |
| `ocr_chain.py` | Scanned OCR decision chain and fallback gating. |
| `helpers.py` | Shared block conversion, corrections, language helper logic. |
| `image_tasks.py` | Embedded image persistence and safe async description calls. |

### `backend/bangladoc_ocr/fallback/`

| Path | Responsibility |
|---|---|
| `llm_fallback.py` | Orchestrates Ollama/Gemini sequence and exposes stats. |
| `llm_tasks/ollama.py` | Ollama availability, request execution, model selection. |
| `llm_tasks/gemini.py` | Gemini API OCR fallback with retry rules. |
| `llm_tasks/parser.py` | LLM text-to-block parsing helpers. |
| `llm_tasks/prompts.py` | Prompt loading and normalization utilities. |
| `llm_tasks/state.py` | Shared fallback counters/status with lock-safe updates. |

### `backend/bangladoc_ocr/nlp/`

| Path | Responsibility |
|---|---|
| `bangla_corrector.py` | Bangla spelling/cleanup/correction pipeline. |
| `confidence_scorer.py` | Confidence scoring and fallback threshold decisions. |
| `numeric_validator.py` | Numeric consistency checks and correction. |
| `unicode_validator.py` | Script ratio checks, text cleaning, contamination stripping. |

### `backend/bangladoc_ocr/extraction/`

| Path | Responsibility |
|---|---|
| `table_handler.py` | Digital and scanned table extraction and normalization. |

### `backend/bangladoc_ocr/output/`

| Path | Responsibility |
|---|---|
| `json_builder.py` | Output persistence, compatibility loading, corpus exports/stats. |

### `backend/bangladoc_ocr/server/`

| Path | Responsibility |
|---|---|
| `app.py` | FastAPI app, routes, progress tracking, warmup, response shaping. |

### `backend/bangladoc_ocr/static/`

| Path | Responsibility |
|---|---|
| `index.html` | Upload UI and result inspection frontend. |

### `backend/bangladoc_ocr/tests/`

| Path | Responsibility |
|---|---|
| `test_bangla_corrector.py` | Corrector behavior tests. |
| `test_confidence_scorer.py` | Confidence and fallback rule tests. |
| `test_numeric_validator.py` | Numeric validator tests. |
| `test_unicode_validator.py` | Unicode/script validator tests. |

## API Contract Summary

- `GET /health` - service liveness.
- `GET /stats` - fallback engine stats.
- `GET /ocr/progress` - current OCR progress.
- `POST /ocr` - process uploaded PDFs.
- `GET /corpus/stats` - corpus aggregate statistics.
- `GET /corpus/export` - download corpus parquet.
- `POST /corpus/verify` - set verification flag for a page.

## Troubleshooting

### 1) No outputs are being saved where expected

- Symptom: OCR succeeds but files are not found in your expected folder.
- Check: `DATA_DIR` in `backend/.env`.
- Behavior: relative `DATA_DIR` is resolved from project root (`bangladoc_surya_clean`), not shell cwd.
- Fix: set an absolute path or correct relative path, then run OCR again.

### 2) Surya is enabled but not used

- Symptom: logs show Surya unavailable or pipeline skips to fallback.
- Check:
  - `SURYA_ENABLED=true` in `backend/.env`.
  - model dependencies are installed in the active environment.
- Runtime behavior: if Surya load fails, chain continues with fallback OCR by design.
- Fix: resolve environment/model install issue, then restart server for clean warmup.

### 3) Ollama fallback not running

- Symptom: fallback skips Ollama and goes to Gemini/EasyOCR.
- Check:
  - Ollama daemon is running.
  - `OLLAMA_BASE_URL` is reachable.
  - a vision-capable model exists locally.
- Quick validation: hit `/stats` and inspect Ollama status/error fields.

### 4) Gemini fallback never runs

- Symptom: Gemini is always marked unavailable.
- Check:
  - `GEMINI_ENABLED=true`
  - `GEMINI_API_KEY` is present and valid.
- Behavior: if disabled or key missing, chain does not call Gemini.

### 5) LLM calls seem too frequent

- Symptom: higher-than-expected API usage.
- Behavior: quick EasyOCR confidence gate runs first; LLM is called only when `needs_api_fallback(...)` returns true.
- Check:
  - document quality and script noise.
  - fallback thresholds in `.env` (`API_FALLBACK_THRESHOLD_*`).

### 6) `/corpus/export` returns not found

- Symptom: API responds with 404 for corpus export.
- Cause: corpus parquet is generated only after at least one successful OCR run with outputs saved.
- Fix: run OCR once, then retry `/corpus/export`.

### 7) Verify endpoint cannot find page JSON

- Symptom: `POST /corpus/verify` returns page not found.
- Behavior: lookup supports both new `page_<n>_<engine>.json` and legacy `page_<n>.json`.
- Check:
  - correct `doc_id` and `page_number`.
  - page JSON exists under `data/output_jsons/<doc_id>/`.

### 8) `.env` changes do not seem applied

- Behavior: config is refreshed at processing start, so most toggles apply on next OCR request.
- Note: startup warmup still reflects server start state; restart server after major engine toggle changes for predictable warmup logs.

## Development and Operations

- For complete setup and commands, use `cmd.txt`.
- Run tests from `backend/`:
  - `./venv/bin/python -m pytest bangladoc_ocr/tests/ -q`
- Keep `backend/.env` local; do not commit secrets.

### Reopen VS Code, Run, and Test (Daily Flow)

From the project root (`bangladoc_surya_clean`):

1. Reopen workspace and activate environment
  - `code .`
  - `source backend/venv/bin/activate`
  - `export PYTORCH_ENABLE_MPS_FALLBACK=1`

2. Refresh before running
  - `git pull`
  - `python -m pip install -e "./backend[dev]"`
  - Restart API and worker after pulling updates

3. Ensure required services are running
  - `docker compose up -d postgres`
  - Start Ollama in another terminal: `ollama serve`

4. Start API and worker (two terminals)
  - API terminal:
    - `cd backend`
    - `source venv/bin/activate`
    - `uvicorn bangladoc_ocr.server.app:app --reload --host 0.0.0.0 --port 8000`
  - Worker terminal:
    - `cd backend`
    - `source venv/bin/activate`
    - `python -m celery -A bangladoc_ocr.celery_app:celery_app worker --loglevel=info --pool=solo -n worker1@%h`

5. Open UI
  - `http://127.0.0.1:8000`
  - Hard refresh browser after frontend/code updates: `Cmd+Shift+R`

6. Run tests
  - `cd backend`
  - `source venv/bin/activate`
  - `pytest -q`

7. Stop services when done
  - Stop API/worker/Ollama with `Ctrl+C` in their terminals
  - `docker compose down`

## Notes on Backward Compatibility

- Merged outputs now use engine suffix naming; loader supports legacy names.
- Per-page JSON lookup supports both new engine-suffixed and older `page_<n>.json` names.
- Config refresh is run per processing invocation to apply `.env` toggles safely.
