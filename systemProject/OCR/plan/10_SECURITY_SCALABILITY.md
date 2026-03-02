# 10 — Security & Scalability

## Handling Large PDFs

```python
# config.py
class PDFLimits:
    MAX_FILE_SIZE_MB = 25           # Hard limit per file
    MAX_PAGES_PER_PDF = 100         # Prevent abuse
    MAX_CONCURRENT_UPLOADS = 5       # Per user
    MAX_DAILY_PAGES = 500            # Per user, cost control

    # For large PDFs: process in batches
    PAGE_BATCH_SIZE = 10             # Process 10 pages at a time
    OCR_TIMEOUT_PER_PAGE = 30        # Seconds

class LargePDFHandler:
    """Process large PDFs in batches to prevent memory issues."""

    async def process_large_pdf(self, document_id: str, total_pages: int):
        """Break large PDF into batches."""

        if total_pages <= PDFLimits.PAGE_BATCH_SIZE:
            # Small PDF — process all at once
            await self.process_batch(document_id, range(total_pages))
        else:
            # Large PDF — batch processing
            for start in range(0, total_pages, PDFLimits.PAGE_BATCH_SIZE):
                end = min(start + PDFLimits.PAGE_BATCH_SIZE, total_pages)
                batch = range(start, end)

                await self.process_batch(document_id, batch)

                # Release memory between batches
                import gc
                gc.collect()

                # Progress update
                ws_publish(document_id, {
                    "step": "ocr",
                    "batch": f"{end}/{total_pages}",
                    "progress": end / total_pages,
                })
```

---

## Rate Limiting

### API-Level Rate Limiting

```python
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",
)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limits by endpoint
@app.post("/api/v1/documents/upload")
@limiter.limit("10/minute")           # Max 10 uploads per minute
async def upload_document(request: Request, file: UploadFile):
    pass

@app.post("/api/v1/cards/{card_id}/regenerate")
@limiter.limit("30/minute")           # Max 30 regenerations per minute
async def regenerate_field(request: Request, card_id: str):
    pass

@app.get("/api/v1/documents")
@limiter.limit("60/minute")           # Max 60 reads per minute
async def list_documents(request: Request):
    pass
```

### User-Level Daily Quota

```python
class QuotaManager:
    """Track and enforce per-user daily API quotas."""

    async def check_quota(self, user_id: str, operation: str) -> bool:
        """Check if user has remaining quota."""
        key = f"quota:{user_id}:{date.today().isoformat()}"

        current = await self.redis.hget(key, operation) or 0
        limits = await self.get_user_limits(user_id)

        if int(current) >= limits[operation]:
            raise HTTPException(429, f"Daily quota exceeded for {operation}")

        return True

    async def consume_quota(self, user_id: str, operation: str, amount: int = 1):
        """Decrement user's quota."""
        key = f"quota:{user_id}:{date.today().isoformat()}"
        await self.redis.hincrby(key, operation, amount)
        await self.redis.expire(key, 86400)  # Auto-expire after 24h

    async def get_user_limits(self, user_id: str) -> dict:
        """Per-user limits (can be different for premium users)."""
        user = await self.db.get_user(user_id)

        if user.role == "admin":
            return {"ocr_pages": 10000, "regenerations": 1000, "uploads": 100}
        elif user.role == "premium":
            return {"ocr_pages": 1000, "regenerations": 200, "uploads": 30}
        else:
            return {"ocr_pages": 100, "regenerations": 50, "uploads": 10}
```

---

## Parallel Processing

```python
import asyncio
from asyncio import Semaphore

class ParallelOCRProcessor:
    """Process multiple pages concurrently with safety limits."""

    GEMINI_CONCURRENCY = 5     # Max parallel Gemini API calls
    IMAGE_CONCURRENCY = 10     # Max parallel image conversions

    async def process_pages_parallel(self, pages: list) -> list:
        """Process pages with controlled concurrency."""

        ocr_semaphore = Semaphore(self.GEMINI_CONCURRENCY)
        img_semaphore = Semaphore(self.IMAGE_CONCURRENCY)

        async def process_one(page):
            async with img_semaphore:
                image_path = await self.convert_to_image(page)

            # Check if native text available (no API needed)
            if page.has_native_text:
                return {"page": page, "text": page.native_text, "cost": 0}

            # Check cache
            cached = self.cache.get(page.image_hash)
            if cached:
                return {"page": page, "text": cached, "cost": 0}

            # Gemini API (rate-limited)
            async with ocr_semaphore:
                text = await self.gemini_ocr(image_path)
                return {"page": page, "text": text, "cost": 0.015}

        results = await asyncio.gather(
            *(process_one(p) for p in pages),
            return_exceptions=True
        )

        return results
```

---

## Background Workers (Celery)

```python
# celery_config.py
from celery import Celery

app = Celery('docint', broker='redis://localhost:6379/0')

app.conf.update(
    # Worker configuration
    worker_concurrency=4,              # Number of worker processes
    worker_prefetch_multiplier=1,      # Process one task at a time (fair distribution)
    worker_max_tasks_per_child=100,    # Restart worker after 100 tasks (memory leak prevention)

    # Task configuration
    task_acks_late=True,               # Acknowledge only after completion
    task_reject_on_worker_lost=True,   # Re-queue if worker dies
    task_time_limit=300,               # Hard limit: 5 minutes per task
    task_soft_time_limit=240,          # Soft limit: 4 minutes (allows cleanup)

    # Queue routing
    task_routes={
        'workers.ocr_worker.*':       {'queue': 'ocr_high',    'priority': 1},
        'workers.embedding_worker.*': {'queue': 'embed_medium', 'priority': 5},
        'workers.scoring_worker.*':   {'queue': 'score_low',    'priority': 9},
    },

    # Result backend
    result_backend='redis://localhost:6379/1',
    result_expires=3600,               # Results expire after 1 hour

    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)
```

### Worker Deployment

```yaml
# docker-compose.yml — worker scaling
services:
  worker-ocr:
    build: .
    command: celery -A workers worker -Q ocr_high -c 4 --loglevel=info
    deploy:
      replicas: 2 # Scale OCR workers independently

  worker-embed:
    build: .
    command: celery -A workers worker -Q embed_medium -c 2 --loglevel=info
    deploy:
      replicas: 1

  worker-score:
    build: .
    command: celery -A workers worker -Q score_low -c 2 --loglevel=info
    deploy:
      replicas: 1

  flower: # Worker monitoring dashboard
    build: .
    command: celery -A workers flower --port=5555
    ports: ["5555:5555"]
```

---

## Horizontal Scaling

### Phase 1 — Single Server

```
┌─────────────────────────────────┐
│ VPS (4 vCPU, 8GB RAM)          │
│                                 │
│ ┌─────┐ ┌───────┐ ┌──────────┐│
│ │ API │ │Worker │ │PostgreSQL││
│ │     │ │       │ │ + Redis  ││
│ └─────┘ └───────┘ └──────────┘│
└─────────────────────────────────┘
Cost: $20-40/month
```

### Phase 3 — Horizontal Scale

```
                    ┌─── API 1 (FastAPI) ───┐
┌─────────┐        │                       │        ┌───────────┐
│ Nginx   │────────┼─── API 2 (FastAPI) ───┼────────│PostgreSQL │
│ (LB)    │        │                       │        │ + Replica │
└─────────┘        └─── API 3 (FastAPI) ───┘        └───────────┘
                                                          │
                    ┌─── OCR Worker 1 ─────┐              │
┌─────────┐        │                       │        ┌───────────┐
│ Redis   │────────┼─── OCR Worker 2 ─────┼────────│ ChromaDB  │
│ (Queue) │        │                       │        │ (Vector)  │
└─────────┘        ├─── Embed Worker 1 ────┤        └───────────┘
                   │                       │
                   └─── Score Worker 1 ────┘

Cost: $100-200/month
```

### Scaling Triggers

| Metric                | Threshold     | Action                 |
| --------------------- | ------------- | ---------------------- |
| API response time     | >2s p95       | Add API instance       |
| OCR queue depth       | >50 tasks     | Add OCR worker         |
| Embedding queue depth | >200 tasks    | Add embed worker       |
| DB connections        | >80% pool     | Add read replica       |
| Memory usage          | >80%          | Increase instance size |
| CPU usage sustained   | >70% for 5min | Scale horizontally     |

---

## API Key Protection

```python
# core/security.py
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os

security = HTTPBearer()

class SecurityManager:
    """Handle authentication and API key protection."""

    def __init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET")

        # NEVER expose external API keys to frontend
        self.gemini_key = os.getenv("GEMINI_API_KEY")  # Server-side only

    async def verify_token(
        self, credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> dict:
        """Verify JWT token from frontend."""
        try:
            payload = jwt.decode(
                credentials.credentials,
                self.jwt_secret,
                algorithms=["HS256"]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")


# Environment variables (NEVER commit these)
# .env file:
# GEMINI_API_KEY=your_key_here
# JWT_SECRET=random_long_string
# DATABASE_URL=postgresql://user:pass@localhost/docint
# REDIS_URL=redis://localhost:6379

# .gitignore:
# .env
# *.key
# *.pem
```

---

## Multi-Tenant Architecture

```python
# All queries scoped to user_id — no data leakage between users

class DocumentRepository:
    """All queries are tenant-scoped."""

    async def get_documents(self, user_id: str, **filters):
        """Get documents — ALWAYS filtered by user_id."""
        query = select(Document).where(
            Document.user_id == user_id,  # ← CRITICAL: Always scope by user
            Document.is_active == True,
        )

        if filters.get("status"):
            query = query.where(Document.status == filters["status"])
        if filters.get("doc_type"):
            query = query.where(Document.detected_type == filters["doc_type"])

        return await self.session.execute(query)

    async def get_document(self, user_id: str, document_id: str):
        """Get single document — verify ownership."""
        doc = await self.session.get(Document, document_id)

        if not doc or doc.user_id != user_id:
            raise HTTPException(404, "Document not found")  # Don't reveal existence

        return doc

# Row-Level Security (PostgreSQL)
# ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
# CREATE POLICY user_isolation ON documents
#   USING (user_id = current_setting('app.current_user_id')::uuid);
```

---

## Data Encryption

```python
# Encrypt sensitive fields at rest
from cryptography.fernet import Fernet

class FieldEncryption:
    """Encrypt sensitive card field values at rest."""

    SENSITIVE_FIELDS = {
        "account_holder_name", "account_or_reference_number",
        "salary_range", "phone", "email"
    }

    def __init__(self):
        self.cipher = Fernet(os.getenv("ENCRYPTION_KEY"))

    def encrypt_if_sensitive(self, field_id: str, value: str) -> str:
        if field_id in self.SENSITIVE_FIELDS:
            return self.cipher.encrypt(value.encode()).decode()
        return value

    def decrypt_if_sensitive(self, field_id: str, value: str) -> str:
        if field_id in self.SENSITIVE_FIELDS:
            return self.cipher.decrypt(value.encode()).decode()
        return value
```

---

## Input Validation

```python
from pydantic import BaseModel, validator, Field
import magic  # python-magic for file type detection

class UploadRequest(BaseModel):
    """Validate upload requests."""

    filename: str = Field(..., max_length=500)
    file_size: int = Field(..., le=25 * 1024 * 1024)  # 25MB max

    @validator("filename")
    def validate_filename(cls, v):
        if not v.lower().endswith(".pdf"):
            raise ValueError("Only PDF files accepted")
        # Sanitize filename
        import re
        return re.sub(r'[^\w\-\.\s\u0980-\u09FF]', '_', v)  # Allow Bangla chars


def validate_file_content(file_bytes: bytes) -> bool:
    """Verify file is actually a PDF (not renamed malware)."""
    mime = magic.from_buffer(file_bytes[:2048], mime=True)
    if mime != "application/pdf":
        raise HTTPException(400, f"File is not a valid PDF (detected: {mime})")

    # Check for PDF header
    if not file_bytes[:5] == b"%PDF-":
        raise HTTPException(400, "Invalid PDF file")

    return True
```
