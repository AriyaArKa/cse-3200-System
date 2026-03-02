# 01 — System Architecture

## Architecture Decision: Modular Monolith → Microservices

**Phase 1 (MVP):** Modular monolith — single deployable unit with clean internal module boundaries.  
**Phase 2+:** Extract hot paths (OCR worker, LLM worker) into independent services.

**Why modular monolith first:**

- Your team is small; microservices add deployment/debugging overhead
- Single DB, single deploy, fast iteration
- Module boundaries let you extract services later painlessly
- Saves $200-500/month in infrastructure costs vs day-one microservices

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/Next.js)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐             │
│  │ Upload   │ │ Card     │ │ Edit     │ │ Dashboard │             │
│  │ Manager  │ │ Viewer   │ │ Panel    │ │           │             │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ REST/WebSocket
┌───────────────────────────▼─────────────────────────────────────────┐
│                     API GATEWAY (FastAPI)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Auth     │ │ Rate     │ │ Request  │ │ WebSocket│              │
│  │ Middleware│ │ Limiter  │ │ Validator│ │ Manager  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                     BACKEND SERVICES LAYER                          │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐          │
│  │ Document    │  │ OCR          │  │ Template         │          │
│  │ Service     │  │ Service      │  │ Service          │          │
│  │             │  │              │  │                  │          │
│  │ - Upload    │  │ - Native PDF │  │ - Type Classify  │          │
│  │ - Validate  │  │ - Gemini OCR │  │ - Card Generate  │          │
│  │ - Convert   │  │ - Cache Mgmt │  │ - Field Fill     │          │
│  │ - Store     │  │ - Batch Proc │  │ - Regenerate     │          │
│  └─────────────┘  └──────────────┘  └──────────────────┘          │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐          │
│  │ Chunking    │  │ Scoring      │  │ Edit             │          │
│  │ Service     │  │ Service      │  │ Service          │          │
│  │             │  │              │  │                  │          │
│  │ - Semantic  │  │ - Field Score│  │ - Version Track  │          │
│  │ - Overlap   │  │ - Doc Score  │  │ - Diff Compute   │          │
│  │ - Metadata  │  │ - Validate   │  │ - Audit Log      │          │
│  └─────────────┘  └──────────────┘  └──────────────────┘          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                     ASYNC / QUEUE LAYER                              │
│  ┌──────────────────────────────────────────┐                       │
│  │  Celery + Redis (MVP) / RabbitMQ (Prod)  │                       │
│  │                                          │                       │
│  │  Queues:                                 │                       │
│  │    ocr_queue      (priority: high)       │                       │
│  │    embedding_queue (priority: medium)    │                       │
│  │    regen_queue     (priority: low)       │                       │
│  │    scoring_queue   (priority: low)       │                       │
│  └──────────────────────────────────────────┘                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                     DATA LAYER                                      │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │PostgreSQL│  │ Redis    │  │ FAISS/   │  │ MinIO/S3 │          │
│  │          │  │          │  │ ChromaDB │  │          │          │
│  │ - Users  │  │ - Cache  │  │          │  │ - PDFs   │          │
│  │ - Docs   │  │ - Session│  │ - Chunks │  │ - Images │          │
│  │ - Cards  │  │ - Queue  │  │ - Embed  │  │ - JSONs  │          │
│  │ - Edits  │  │ - OCR $  │  │ - Search │  │          │          │
│  │ - Logs   │  │          │  │          │  │          │          │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack Decision Matrix

| Layer              | MVP Choice          | Production Choice                    | Reasoning                                                    |
| ------------------ | ------------------- | ------------------------------------ | ------------------------------------------------------------ |
| **Frontend**       | React + Tailwind    | Next.js + Tailwind + shadcn/ui       | SSR for SEO, component library speed                         |
| **API**            | FastAPI (Python)    | FastAPI (Python)                     | Async native, Pydantic validation, your team knows Python    |
| **Queue**          | Celery + Redis      | Celery + RabbitMQ                    | Redis is free locally; RabbitMQ for reliability at scale     |
| **Primary DB**     | SQLite → PostgreSQL | PostgreSQL + read replicas           | Start SQLite for dev speed, migrate to PG before launch      |
| **Cache**          | Redis               | Redis Cluster                        | OCR result caching, session, rate limiting                   |
| **Vector DB**      | FAISS (local)       | ChromaDB (local) or Pinecone (cloud) | FAISS = zero cost; ChromaDB = easier API; Pinecone = managed |
| **Object Storage** | Local filesystem    | MinIO (self-hosted) or S3            | MinIO = S3-compatible, free self-hosted                      |
| **OCR/LLM**        | Gemini 2.5 Flash    | Gemini Flash + Ollama fallback       | Flash for quality; local Ollama for cost reduction           |
| **Embedding**      | all-MiniLM-L6-v2    | all-MiniLM-L6-v2                     | Free, 384-dim, good quality, runs locally                    |
| **Deployment**     | Docker Compose      | Docker Compose → K8s                 | Single machine first, K8s when you need horizontal scaling   |
| **Monitoring**     | Logging             | Prometheus + Grafana                 | Industry standard, free                                      |

---

## Module Boundary Design

```python
# Project structure (modular monolith)
app/
├── main.py                    # FastAPI app entry point
├── config.py                  # Settings (pydantic-settings)
├── dependencies.py            # Dependency injection
│
├── api/                       # API layer (thin controllers)
│   ├── v1/
│   │   ├── documents.py       # Upload, list, delete endpoints
│   │   ├── cards.py           # Card CRUD, regeneration endpoints
│   │   ├── edits.py           # User edit endpoints
│   │   └── auth.py            # Auth endpoints
│   └── websocket.py           # Real-time progress updates
│
├── services/                  # Business logic (NO framework deps)
│   ├── document_service.py    # Upload validation, orchestration
│   ├── ocr_service.py         # OCR pipeline (native + Gemini)
│   ├── chunking_service.py    # Text → chunks
│   ├── embedding_service.py   # Chunks → vectors
│   ├── template_service.py    # Type classification + card generation
│   ├── scoring_service.py     # Confidence calculation
│   ├── regeneration_service.py# Field/section/card regen
│   └── edit_service.py        # Edit tracking, versioning
│
├── workers/                   # Celery async tasks
│   ├── ocr_worker.py
│   ├── embedding_worker.py
│   └── scoring_worker.py
│
├── models/                    # SQLAlchemy ORM models
│   ├── user.py
│   ├── document.py
│   ├── page.py
│   ├── ocr_result.py
│   ├── chunk.py
│   ├── template_card.py
│   ├── card_field.py
│   ├── edit_history.py
│   └── regen_log.py
│
├── schemas/                   # Pydantic request/response schemas
│   ├── document_schema.py
│   ├── card_schema.py
│   └── edit_schema.py
│
├── repositories/              # Database access layer
│   ├── document_repo.py
│   ├── card_repo.py
│   └── vector_repo.py
│
├── core/                      # Cross-cutting concerns
│   ├── cache.py               # Redis wrapper
│   ├── storage.py             # File storage abstraction
│   ├── security.py            # JWT, API key management
│   └── exceptions.py          # Custom exceptions
│
├── templates/                 # Card template definitions (JSON)
│   ├── student_support.json
│   ├── job_eligibility.json
│   ├── government_policy.json
│   ├── financial_health.json
│   └── meeting_tracker.json
│
└── migrations/                # Alembic DB migrations
    └── versions/
```

---

## Async Processing Architecture

### What runs sync vs async

| Operation               | Sync/Async         | Why                                            |
| ----------------------- | ------------------ | ---------------------------------------------- |
| PDF upload & validation | **Sync**           | Fast (<100ms), user needs immediate feedback   |
| PDF → image conversion  | **Async (Celery)** | CPU-intensive, 2-30s per PDF                   |
| Native text extraction  | **Async (Celery)** | I/O bound, runs parallel with image conversion |
| Gemini OCR per page     | **Async (Celery)** | API call, 2-5s per page, rate-limited          |
| Chunking                | **Async (Celery)** | CPU-bound, runs after OCR                      |
| Embedding generation    | **Async (Celery)** | CPU/GPU bound                                  |
| Template card filling   | **Async (Celery)** | May need LLM call                              |
| Confidence scoring      | **Async (Celery)** | Depends on multiple data sources               |
| User edits              | **Sync**           | Instant feedback needed                        |
| Field regeneration      | **Async (Celery)** | LLM call required                              |
| Full card regeneration  | **Async (Celery)** | Multiple LLM calls                             |

### Queue Priority System

```python
# celery_config.py
from celery import Celery

app = Celery('docint')
app.conf.update(
    task_routes={
        'workers.ocr_worker.*': {'queue': 'ocr_high'},
        'workers.embedding_worker.*': {'queue': 'embed_medium'},
        'workers.scoring_worker.*': {'queue': 'score_low'},
    },
    task_default_queue='default',
    worker_prefetch_multiplier=1,  # Fair scheduling
    task_acks_late=True,           # Re-queue on worker crash
    task_reject_on_worker_lost=True,
)
```

---

## Deployment Strategy

### Phase 1 — Single Server (MVP)

```yaml
# docker-compose.yml (MVP)
version: "3.8"
services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, redis]

  worker:
    build: .
    command: celery -A workers worker --loglevel=info -Q ocr_high,embed_medium,score_low
    depends_on: [db, redis]

  db:
    image: postgres:16-alpine
    volumes: [pg_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
```

**Estimated cost:** $20-40/month (single VPS: 4 vCPU, 8GB RAM)

### Phase 3 — Horizontal Scaling

```
                    ┌──── API Instance 1 ────┐
Load Balancer ──────┼──── API Instance 2 ────┼──── PostgreSQL (Primary)
  (Nginx)           └──── API Instance 3 ────┘       │
                                                      └── Read Replica
                    ┌──── OCR Worker 1 ──────┐
  Redis ────────────┼──── OCR Worker 2 ──────┤
  (Queue)           ├──── Embed Worker 1 ────┤
                    └──── Score Worker 1 ────┘
```

---

## Communication Patterns

| Pattern        | Use Case                                  | Implementation                     |
| -------------- | ----------------------------------------- | ---------------------------------- |
| **REST**       | CRUD operations, uploads                  | FastAPI endpoints                  |
| **WebSocket**  | Real-time OCR progress, live card updates | FastAPI WebSocket + Redis PubSub   |
| **Task Queue** | Heavy async work (OCR, embedding)         | Celery + Redis/RabbitMQ            |
| **Event Bus**  | Service-to-service notifications          | Redis PubSub (MVP) → Kafka (scale) |

### WebSocket Progress Example

```python
# Real-time pipeline progress to frontend
@app.websocket("/ws/pipeline/{document_id}")
async def pipeline_progress(websocket: WebSocket, document_id: str):
    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"pipeline:{document_id}")

    async for message in pubsub.listen():
        if message["type"] == "message":
            await websocket.send_json(json.loads(message["data"]))
            # Example payload:
            # {"step": "ocr", "page": 3, "total": 10, "status": "processing"}
            # {"step": "scoring", "progress": 0.8, "status": "complete"}
```
