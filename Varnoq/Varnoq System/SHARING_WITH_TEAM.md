# Sharing BanglaDOC with Your Team

This document explains how to share this project with teammates who are on different OS and have different setups.

---

## Quick Links for Teammates

### 🖥️ Windows Users
→ Read **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**
- **Option A: Docker** (5 minutes, easiest)
- **Option B: Native Python** (20 minutes, more control)

### 🐧 Linux Users  
→ Read **[README.md](README.md#getting-started-teammate-onboarding)** → "Native Setup (Windows/Linux/Mac)"
- Same as macOS, just use `apt-get` for system packages

### 🍎 macOS Users
→ Read **[README.md](README.md#getting-started-teammate-onboarding)** → "Native Setup (Windows/Linux/Mac)"
→ Or use **[Docker](README.md#native-setup-windowslinuxmac)** for simplest setup

### Any OS (Recommended)
→ **Docker Setup** in [README.md](README.md#-quick-start---docker-recommended-for-any-os)
- Same setup works on Windows/Mac/Linux
- No Python/dependencies conflicts
- Best for team consistency

---

## How to Share with Your Team

### Step 1: Prepare the Repository

Make sure these files are committed and pushed:
```bash
git add README.md cmd.txt WINDOWS_SETUP.md SHARING_WITH_TEAM.md
git commit -m "Add comprehensive onboarding guides for team"
git push
```

### Step 2: Send These Links to Your Team

#### For the Whole Team
```
Main Documentation:
1. README.md - Full technical overview + diagrams
2. WINDOWS_SETUP.md - For Windows teammates
3. cmd.txt - Command reference for daily use

Quick Links:
- Docker Quick Start: https://github.com/your-repo/.../README.md#-quick-start---docker-recommended-for-any-os
- Native Setup: https://github.com/your-repo/.../README.md#-native-setup-windowslinuxmac
- Troubleshooting: https://github.com/your-repo/.../README.md#-troubleshooting-teammate-setup
```

#### For Windows Teammates Specifically
```
Start here: WINDOWS_SETUP.md

Choose Option A (Docker - 5 min) or Option B (Native - 20 min)
All prerequisites and step-by-step instructions included.
```

#### For Mac/Linux Teammates
```
Start here: README.md → "Getting Started (Teammate Onboarding)"

Choose Option A (Docker) or Option B (Native Setup)
```

### Step 3: Recommended First Meeting

Arrange a 15-minute sync where you:
1. Share the repository link
2. Have them run setup while you're on call (can debug together)
3. Once running, show them the UI at http://localhost:8000
4. Have them upload a test PDF to verify everything works

---

## What Files to Share

**Essential:**
- `README.md` - Architecture, API docs, troubleshooting
- `cmd.txt` - Command reference
- `WINDOWS_SETUP.md` - For Windows teammates
- `.env.example` - Environment template (they copy to `.env`)
- `docker-compose.yml` - For Docker users
- `pyproject.toml` - Dependencies

**Don't Share:**
- `.env` (contains local secrets) - They create their own
- `backend/venv/` - They create their own virtual environment
- `data/` - Generated outputs, not source code
- `__pycache__/`, `.pytest_cache/`, etc. - Ignored by .gitignore

---

## Team Member Setup Timeline

### Before Kickoff
1. Share repository link
2. Ask them to choose: Docker or Native setup
3. Have them install prerequisites while you're available

### Day 1 (15 min)
1. They follow WINDOWS_SETUP.md (or README section for their OS)
2. Services should be running by end
3. They test by uploading a PDF

### Day 2+
1. They read README.md diagrams to understand architecture
2. They review cmd.txt for daily commands
3. They start contributing code

---

## Docker - Why It's Best for Teams

If your team is mixed OS (Windows/Mac/Linux):

**Pros:**
- ✅ Same setup for everyone
- ✅ No "works on my machine" issues
- ✅ No Python version conflicts
- ✅ No system dependencies headaches
- ✅ Instant PostgreSQL/Redis setup
- ✅ Easy to reset with `docker compose down && docker compose up`

**Con:**
- Slight performance overhead (negligible for OCR)

**Command for team:**
```bash
# One command to start everything
docker compose up -d

# One command to stop everything  
docker compose down

# One command to reset (nuke all data)
docker compose down -v && docker compose up -d
```

---

## Monitoring Team Progress

### Checklist for Each Teammate After Setup

Ask them to verify:
- [ ] Repository cloned
- [ ] Services started (API, Worker, Ollama)
- [ ] Can access http://localhost:8000
- [ ] Can upload a PDF and see job complete
- [ ] Can read output in `data/output_jsons/`
- [ ] Tests pass: `pytest -q`

### Common First-Time Issues

See **[WINDOWS_SETUP.md - Common Issues](WINDOWS_SETUP.md#common-issues-on-windows)** and **[README.md Troubleshooting](README.md#-troubleshooting-teammate-setup)** for solutions.

---

## Daily Workflow for Your Team

Once they're set up, they use:

**Every day:**
1. `git pull` (get latest code)
2. Start services (see cmd.txt or README)
3. Open http://localhost:8000
4. Test changes
5. Commit and push

**If they update dependencies:**
```bash
# After pulling new code
docker compose build  # if using Docker
# or
python -m pip install -e "./backend[dev]"  # if native
```

---

## Troubleshooting for Team

### Issue: "Port 8000 already in use"
**Cause:** Previous session still running
**Solution:** 
```bash
# Docker: docker compose down
# Native: Ctrl+C in API window and restart
```

### Issue: "Event loop is closed" (Celery)
**Cause:** Old worker process still running
**Solution:**
```bash
# Kill old workers
pkill -f "celery -A"  # or use Task Manager on Windows
# Restart worker
```

### Issue: "PostgreSQL connection refused"
**Cause:** Database not running
**Solution:**
```bash
# Docker: docker compose up -d
# Windows: Services → postgresql-15 → Start
# Mac: brew services start postgresql
```

### Issue: "Surya models not available"
**Cause:** Model files not downloaded
**Solution:**
```bash
python -m pip install --upgrade surya-ocr
python -c "from surya.foundation import FoundationPredictor; FoundationPredictor.from_pretrained('surya')"
```

---

## Onboarding Checklist

Before first day of teammate contributions:

- [ ] Repository access granted (GitHub/GitLab)
- [ ] README.md reviewed by them
- [ ] WINDOWS_SETUP.md (if Windows) or native setup completed
- [ ] Services running: API, Worker, Ollama
- [ ] UI accessible at http://localhost:8000
- [ ] Test PDF processed successfully
- [ ] Tests passing: `pytest -q`
- [ ] They understand git workflow (pull requests, commits)
- [ ] They know where to find help (README, cmd.txt, WINDOWS_SETUP.md)

---

## Ongoing Support

### Weekly Check-ins
- Any setup issues?
- Any environment conflicts?
- Any features they need?

### Monthly
- Update dependencies: `python -m pip install --upgrade`
- Clean old data: `docker compose down -v && docker compose up -d`
- Backup corpus data from `data/corpus/`

---

## Questions from Team?

**"Should I use Docker or native?"**
→ Docker if: mixed OS team, no Python experience
→ Native if: want to debug deeper, modify core deps

**"How do I modify code?"**
→ Edit files in `backend/bangladoc_ocr/`
→ API auto-reloads, worker needs restart

**"Why is OCR taking so long?"**
→ Normal: Surya + Ollama can take 30-60s per page
→ Faster: disable Surya if only English content

**"Can I use Windows Subsystem for Linux?"**
→ Yes, but Docker Desktop is simpler

**"What if I don't have 8GB RAM?"**
→ Reduce: Set `SURYA_ENABLED=false` in .env
→ Or use smaller Ollama model

---

## Summary

**For Easy Sharing:**
1. Copy these 3 files to your teammate:
   - README.md
   - WINDOWS_SETUP.md (if Windows)
   - cmd.txt

2. Tell them:
   - Windows? → Read WINDOWS_SETUP.md
   - Mac/Linux? → Read README.md "Getting Started"
   - Prefer Docker? → Use docker compose (1 command)

3. Have them test by uploading a PDF

**Success = They can run `docker compose up -d` or the native equivalent, access the UI, and process a PDF without help.**

Good luck with your team! 🚀
