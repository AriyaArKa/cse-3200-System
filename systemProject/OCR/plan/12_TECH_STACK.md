# 12 — Tech Stack Recommendation

## Final Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        RECOMMENDED STACK                        │
├──────────────┬──────────────────────┬───────────────────────────┤
│ Layer        │ Technology           │ Why                       │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Frontend     │ React + Tailwind     │ Your team knows it,       │
│              │ + shadcn/ui          │ component library saves   │
│              │                      │ weeks of UI work          │
├──────────────┼──────────────────────┼───────────────────────────┤
│ API/Backend  │ FastAPI (Python)     │ Async native, Pydantic    │
│              │                      │ validation, auto-docs,    │
│              │                      │ your existing code is Py  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ ORM          │ SQLAlchemy 2.0       │ Async support, mature,    │
│              │ + Alembic migrations │ works with SQLite + PG    │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Database     │ SQLite (MVP) →       │ Zero setup for dev.       │
│              │ PostgreSQL (prod)    │ PG for production scale.  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Cache        │ Redis                │ OCR cache, sessions,      │
│              │                      │ queue broker, rate limits │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Queue        │ Celery + Redis       │ Python native, battle-    │
│              │ (→ RabbitMQ at scale)│ tested, easy scaling      │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Vector DB    │ ChromaDB (local)     │ Free, persistent, built-  │
│              │                      │ in metadata filtering,    │
│              │                      │ Python-native API         │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Embeddings   │ all-MiniLM-L6-v2    │ Free, local, 384-dim,     │
│              │ (sentence-transform) │ good quality, fast (CPU)  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ OCR/LLM      │ Gemini 2.5 Flash    │ Best multimodal OCR,      │
│ (Primary)    │                      │ good Bangla support,      │
│              │                      │ reasonable pricing        │
├──────────────┼──────────────────────┼───────────────────────────┤
│ LLM          │ Ollama + Llama 3.1  │ Free locally, good for    │
│ (Secondary)  │ (Phase 3+)          │ summarization, classify   │
├──────────────┼──────────────────────┼───────────────────────────┤
│ PDF Parsing  │ PyMuPDF (fitz)      │ Fast native text extract, │
│              │ + pdfplumber        │ table extraction, free     │
│              │ + pdf2image/poppler │ Image conversion (exist.)  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Storage      │ Local filesystem →  │ Local = free. MinIO =      │
│              │ MinIO (Phase 3)     │ S3-compatible, self-hosted │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Auth         │ JWT (python-jose)   │ Stateless, simple, works  │
│              │ + bcrypt            │ with SPA frontend          │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Deployment   │ Docker Compose      │ Single command deploy,     │
│              │ (→ K8s at scale)    │ reproducible environments  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Monitoring   │ Prometheus +        │ Free, industry standard,   │
│              │ Grafana (Phase 3)   │ great alerting             │
├──────────────┼──────────────────────┼───────────────────────────┤
│ CI/CD        │ GitHub Actions      │ Free for open source,      │
│              │                      │ integrated with your repo  │
├──────────────┼──────────────────────┼───────────────────────────┤
│ Testing      │ pytest + httpx      │ FastAPI testing standard   │
│              │ + Locust (load)     │                            │
└──────────────┴──────────────────────┴───────────────────────────┘
```

---

## Why NOT Other Options

| Alternative                       | Why Rejected                                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------------------- |
| **Django** instead of FastAPI     | Heavier, sync by default, you don't need admin panel                                         |
| **Express.js** instead of FastAPI | Your existing code is Python, switching languages slows you down                             |
| **Next.js** instead of React      | SSR unnecessary for a dashboard app, adds complexity                                         |
| **MongoDB** instead of PostgreSQL | Your data is highly relational (cards→fields→edits). SQL is better.                          |
| **Pinecone** instead of ChromaDB  | Costs $70+/month. ChromaDB is free and handles your scale easily.                            |
| **OpenAI** instead of Gemini      | Gemini 2.5 Flash is cheaper for multimodal OCR and has good Bangla support.                  |
| **Kubernetes** for MVP            | Massive overkill. Docker Compose handles single-server fine.                                 |
| **RabbitMQ** for MVP              | Redis as broker is simpler. Switch to RabbitMQ only if you need message guarantees at scale. |
| **FAISS** instead of ChromaDB     | FAISS lacks built-in metadata filtering and persistence. More work for same result.          |

---

## Python Dependencies (requirements.txt)

```
# Core
fastapi==0.115.*
uvicorn[standard]==0.34.*
pydantic==2.*
pydantic-settings==2.*

# Database
sqlalchemy[asyncio]==2.*
alembic==1.*
asyncpg==0.30.*           # PostgreSQL async driver
aiosqlite==0.20.*         # SQLite async driver (dev)

# Cache & Queue
redis==5.*
celery==5.*

# OCR & PDF
google-genai==1.*         # Gemini SDK
PyMuPDF==1.*              # Native PDF text extraction
pdfplumber==0.11.*        # Table extraction
pdf2image==1.*            # PDF → image (your existing dep)
Pillow==11.*              # Image handling

# Vector DB & Embeddings
chromadb==0.5.*
sentence-transformers==3.*

# Auth & Security
python-jose[cryptography]==3.*
passlib[bcrypt]==1.*
python-multipart==0.0.*

# Utilities
python-dotenv==1.*
httpx==0.27.*             # Async HTTP client
python-magic==0.*         # File type detection

# Monitoring (Phase 3)
prometheus-fastapi-instrumentator==7.*

# Testing
pytest==8.*
pytest-asyncio==0.24.*
httpx==0.27.*             # For TestClient
```

---

## Monthly Cost Projection

| Phase              | Infrastructure | API Costs             | Total          |
| ------------------ | -------------- | --------------------- | -------------- |
| **MVP** (dev)      | $0 (local)     | $10-20 (Gemini)       | **$10-20**     |
| **MVP** (deployed) | $20-40 (VPS)   | $20-50                | **$40-90**     |
| **Phase 2**        | $40-60         | $10-30 (with caching) | **$50-90**     |
| **Phase 3**        | $100-200       | $50-150               | **$150-350**   |
| **Phase 4**        | $200-500       | Revenue covers costs  | **Profitable** |

---

## Repository Structure (Final)

```
cse-3200-System/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── api/v1/
│   │   ├── services/
│   │   ├── workers/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── core/
│   │   ├── templates/
│   │   └── migrations/
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── celery_config.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload/
│   │   │   ├── CardViewer/
│   │   │   ├── FieldEditor/
│   │   │   └── Dashboard/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/      # API client
│   │   └── utils/
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── docs/
│   ├── api.md
│   ├── architecture.md
│   └── deployment.md
├── plan/                   # This planning directory
└── README.md
```
