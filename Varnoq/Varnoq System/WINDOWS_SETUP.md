# BanglaDOC Surya Clean - Windows 10/11 Setup Guide

This guide is for teammates on **Windows 10/11**. Choose **Option A (Docker)** for easiest setup, or **Option B (Native)** for more control.

---

## Option A: Docker Setup (Recommended - 5 minutes)

### Prerequisites
- **Docker Desktop** from https://www.docker.com/products/docker-desktop
- 8+ GB RAM, 20+ GB disk space
- Windows 10 Pro/Enterprise or Windows 11

### Steps

**1. Install Docker Desktop**
- Download and install from https://www.docker.com/products/docker-desktop
- Launch Docker Desktop (wait for it to fully start - check system tray)
- Verify: Open PowerShell and run:
  ```powershell
  docker --version
  docker run hello-world
  ```

**2. Clone Repository**
```powershell
# Open PowerShell in your desired folder
cd C:\Users\YourName\Documents
git clone <repo-url>
cd "Varnoq System"
```

**3. Start All Services**
```powershell
# This builds and runs everything
docker compose up -d

# Wait 30 seconds for services to start
Start-Sleep -Seconds 30

# Check services
docker ps
```

**4. Open UI**
```powershell
# Open in browser
start http://localhost:8000

# Or manually: open http://localhost:8000 in Chrome/Edge/Firefox
```

**5. Test OCR**
- Click "Upload & OCR" in browser
- Select a PDF
- Wait for job to complete
- Verify output appears in UI

**6. Stop Services**
```powershell
docker compose down
```

---

## Option B: Native Python Setup (20 minutes)

### Prerequisites

**Install these (one time only):**

1. **Python 3.12+**
   - Download: https://www.python.org/downloads/
   - ✅ Check: "Add Python to PATH" during installation
   - Verify: Open PowerShell, type `python --version`

2. **Git Bash** (for Unix-like commands)
   - Download: https://git-scm.com/download/win
   - Install with default options

3. **PostgreSQL 15+** (Database)
   - Option 1: https://www.postgresql.org/download/windows/
   - Option 2: Use Docker (see below)

4. **Ollama** (Optional, for vision models)
   - Download: https://ollama.ai/download
   - After install, run: `ollama pull qwen2.5vl:7b`

5. **VS Code** (Editor)
   - https://code.visualstudio.com/
   - Install Python extension

### Full Setup Process

**Step 1: Get the Code**
```powershell
cd C:\Users\YourName\Documents
git clone <repo-url>
cd "Varnoq System"
```

**Step 2: Setup Database (PostgreSQL)**

**Option A: Local PostgreSQL**
- Open Services app (Windows Key + R, type `services.msc`)
- Find "postgresql-15"
- Right-click → "Start" (if not running)
- Verify it's running

**Option B: PostgreSQL in Docker** (Simpler)
```powershell
# Run this once to start database
docker run -d `
  --name bangladoc-db `
  -e POSTGRES_USER=bangladoc `
  -e POSTGRES_PASSWORD=arka `
  -e POSTGRES_DB=bangladoc `
  -p 5432:5432 `
  postgres:15

# Stop database later:
docker stop bangladoc-db
```

**Step 3: Create Python Virtual Environment**
```powershell
cd "Varnoq System"

# Create venv
python -m venv backend/venv

# Activate venv (you'll see (venv) in your prompt)
backend/venv/Scripts/Activate.ps1

# If you get execution policy error, run this once:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Step 4: Install Dependencies**
```powershell
# Make sure venv is active (check for (venv) in prompt)

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel

# Install backend package and all dependencies
python -m pip install -e "./backend[dev]"

# Verify Surya (may take a minute to download models)
python -c "from surya.recognition import RecognitionPredictor; print('✓ Surya OK')"
```

**Step 5: Configuration**
```powershell
# Copy environment file
copy backend\.env.example backend\.env

# Edit backend\.env in VS Code
code backend\.env
```

**In backend\.env, make sure these are set:**
```ini
# Database
DATABASE_URL=postgresql://bangladoc:arka@localhost:5432/bangladoc
REDIS_URL=redis://localhost:6379/0

# OCR
SURYA_ENABLED=true
OLLAMA_ENABLED=true
GEMINI_ENABLED=false

# Data output
DATA_DIR=../data
```

**Step 6: Start Services** (3 PowerShell windows)

**Window 1: API Server**
```powershell
cd "Varnoq System\backend"
backend/venv/Scripts/Activate.ps1
uvicorn bangladoc_ocr.server.app:app --reload --host 0.0.0.0 --port 8000

# You should see: Uvicorn running on http://0.0.0.0:8000
```

**Window 2: Celery Worker**
```powershell
cd "Varnoq System\backend"
backend/venv/Scripts/Activate.ps1
python -m celery -A bangladoc_ocr.celery_app:celery_app worker --loglevel=info --pool=solo -n worker1@%h

# You should see: worker1@COMPUTERNAME ready
```

**Window 3: Ollama** (Optional)
```powershell
ollama serve

# You should see: Listening on 127.0.0.1:11434
```

**Step 7: Open UI**
```powershell
# In browser
start http://localhost:8000
```

**Step 8: Test**
- Register new account (first time only)
- Login
- Upload a PDF
- Click "Upload & OCR"
- Wait for job to complete (watch Celery window for progress)

**Step 9: Stop Everything**
```powershell
# In each terminal: Ctrl+C
# If using Docker DB: docker stop bangladoc-db
```

---

## Switching Between Sessions

### Starting Again Tomorrow
```powershell
# This assumes: Python, Ollama, PostgreSQL already installed

# 1. Open 3 PowerShell windows in Varnoq System folder

# Window 1: API
cd backend
backend/venv/Scripts/Activate.ps1
uvicorn bangladoc_ocr.server.app:app --reload --host 0.0.0.0 --port 8000

# Window 2: Worker
cd backend
backend/venv/Scripts/Activate.ps1
python -m celery -A bangladoc_ocr.celery_app:celery_app worker --loglevel=info --pool=solo -n worker1@%h

# Window 3: Ollama (optional)
ollama serve

# Browser: http://localhost:8000
```

---

## Installing Packages Later

If you need to install additional Python packages:

```powershell
# Make sure venv is active
cd "Varnoq System"
backend/venv/Scripts/Activate.ps1

# Install new package
python -m pip install package-name

# Save to requirements
python -m pip freeze > requirements.txt
```

---

## Common Issues on Windows

### ❌ "python: The term 'python' is not recognized"
**Fix:** Python not in PATH
- Reinstall Python and check✅ "Add Python to PATH" during setup
- Or add manually to PATH environment variable

### ❌ "Execution Policy: Cannot be loaded"
**Fix:** Run this once in PowerShell (as admin):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ "PostgreSQL connection refused"
**Fix:** Start database
```powershell
# Open Services app
# Find postgresql-15
# Right-click → Start

# Or use Dcoker: docker start bangladoc-db
```

### ❌ "Port 8000 already in use"
**Fix:** Kill previous process
```powershell
$process = Get-Process | Where-Object { $_.Handles -like "*8000*" }
Stop-Process -Id $process.Id -Force
```

### ❌ "Event loop is closed" (Celery error)
**Fix:** Use latest code and restart worker
```powershell
# Stop worker (Ctrl+C)
# Start new worker
python -m celery -A bangladoc_ocr.celery_app:celery_app worker --loglevel=info --pool=solo -n worker1@%h
```

### ❌ "Surya models not found"
**Fix:** Download models
```powershell
python -m pip install --upgrade surya-ocr
python -c "from surya.foundation import FoundationPredictor; f=FoundationPredictor.from_pretrained('surya')"
```

### ❌ "Ollama timeout"
**Fix:** Make sure Ollama is running
```powershell
# Check: Is Ollama running? (look for window)
# If not: ollama serve

# Test connection:
curl http://localhost:11434/api/tags
```

---

## Tips for Development

### Editing Code
```powershell
# Open in VS Code
code .

# API server will auto-reload on file changes
# For worker changes: restart worker manually
```

### Viewing Logs
```powershell
# API logs: Check API window
# Worker logs: Check Worker window (INFO level)
# Database logs: docker logs bangladoc-db (if using Docker)

# Full Celery debug mode:
python -m celery -A bangladoc_ocr.celery_app:celery_app worker --loglevel=debug --pool=solo
```

### Running Tests
```powershell
cd backend
backend/venv/Scripts/Activate.ps1
pytest -q
```

### Clearing Data
```powershell
# Remove test outputs
rmdir /s data\output_jsons
rmdir /s data\output_texts
rmdir /s data\merged_outputs
rmdir /s data\output_images
```

---

## Need Help?

Check these in order:
1. **README.md** - Full technical documentation
2. **cmd.txt** - Command reference
3. **Backend logs** - Check Worker and API terminal windows for errors
4. **Database** - Check PostgreSQL is running
5. **Network** - If using remote Ollama, check IP/port

---

## Next Steps

Once setup is working:
1. Read **README.md** for architecture overview
2. Check **cmd.txt** for daily workflow
3. Look at step-by-step diagrams in README for how OCR pipeline works
4. Explore code in **backend/bangladoc_ocr/** to understand modules
5. Run tests: `pytest -q` to verify no issues

Happy coding! 🚀
