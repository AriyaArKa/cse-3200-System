# 11 — MVP → Production Roadmap

## Phase Overview

```
Phase 1 (MVP)          Phase 2 (Optimize)     Phase 3 (Scale)        Phase 4 (Enterprise)
4-6 weeks              4-6 weeks              6-8 weeks              8-12 weeks
──────────────────────────────────────────────────────────────────────────────────────────
│ Core pipeline        │ Cost reduction        │ Horizontal scale     │ Multi-tenant
│ Basic UI             │ Caching layers        │ Background workers   │ SLA monitoring
│ 5 templates          │ Hybrid OCR            │ Advanced scoring     │ Admin dashboard
│ Single user          │ Confidence scoring    │ Version history      │ Custom templates
│ SQLite               │ PostgreSQL            │ Load balancer        │ API marketplace
│ $40/mo               │ $100/mo               │ $200-500/mo          │ $500-2000/mo
```

---

## Phase 1 — MVP (4-6 Weeks)

### Goal

Working end-to-end pipeline: Upload → OCR → Template Card → Download

### Week 1-2: Backend Foundation

| Task                         | Details                                     | Priority |
| ---------------------------- | ------------------------------------------- | -------- |
| FastAPI project setup        | Project structure, config, dependencies     | P0       |
| Database models (SQLAlchemy) | Users, Documents, Pages, OCR Results, Cards | P0       |
| PDF upload endpoint          | Validation, storage, deduplication by hash  | P0       |
| PDF → image conversion       | Migrate existing `pdf.py` logic             | P0       |
| Gemini OCR integration       | Migrate existing `main.py` logic            | P0       |
| JSON merge logic             | Migrate existing merge logic                | P0       |

### Week 2-3: Template Engine

| Task                     | Details                                      | Priority |
| ------------------------ | -------------------------------------------- | -------- |
| Document type classifier | Rule-based (keyword matching) for MVP        | P0       |
| Template card system     | Load 5 templates from JSON files             | P0       |
| Field extraction         | Basic: send full text + ask for field values | P0       |
| Card creation API        | POST /cards, GET /cards/{id}                 | P0       |
| Basic field filling      | LLM-based extraction for all fields          | P0       |

### Week 3-4: Frontend (React)

| Task              | Details                           | Priority |
| ----------------- | --------------------------------- | -------- |
| Upload page       | Drag-drop PDF upload              | P0       |
| Processing status | Show pipeline progress (polling)  | P0       |
| Card viewer       | Display template card with fields | P0       |
| Field edit        | Inline text editing               | P0       |
| Download JSON     | Export final card as JSON         | P0       |

### Week 4-5: Integration & Polish

| Task               | Details                                   | Priority |
| ------------------ | ----------------------------------------- | -------- |
| End-to-end testing | Upload → Card → Download flow             | P0       |
| Error handling     | Graceful failures, user-friendly messages | P0       |
| Basic auth         | JWT token, login/register                 | P1       |
| Docker setup       | Dockerfile + docker-compose               | P1       |
| README & docs      | Setup instructions, API docs (Swagger)    | P1       |

### MVP Deliverables

- [ ] Upload 1-5 PDFs
- [ ] Automatic OCR (Gemini 2.5 Flash)
- [ ] Auto-detect document type (5 types)
- [ ] Generate template card
- [ ] View and edit card fields
- [ ] Download final JSON
- [ ] Basic user authentication

### MVP Tech Stack

| Component | Tool                      |
| --------- | ------------------------- |
| Backend   | FastAPI + SQLAlchemy      |
| Database  | SQLite (dev) → PostgreSQL |
| Frontend  | React + Tailwind CSS      |
| OCR       | Gemini 2.5 Flash          |
| Storage   | Local filesystem          |
| Auth      | JWT (python-jose)         |

---

## Phase 2 — Optimization (4-6 Weeks)

### Goal

Reduce costs by 60-80%, add caching, confidence scoring, basic regeneration.

### Week 1-2: OCR Cost Reduction

| Task                       | Details                                   | Savings                  |
| -------------------------- | ----------------------------------------- | ------------------------ |
| Native PDF text extraction | PyMuPDF + pdfplumber pre-step             | **50-80%** OCR calls     |
| OCR result caching         | Redis cache by page hash                  | **20-30%** on re-uploads |
| Adaptive DPI               | 150/200/300 based on content              | **30-50%** on token cost |
| Prompt optimization        | Shorter prompts + JSON schema enforcement | **40%** token reduction  |
| Duplicate page detection   | Skip OCR for identical pages              | **5-10%** on long docs   |

### Week 2-3: Chunking & Vector DB

| Task                          | Details                             | Priority |
| ----------------------------- | ----------------------------------- | -------- |
| Semantic chunker              | Section-aware text splitting        | P0       |
| ChromaDB setup                | Local persistent storage            | P0       |
| Embedding service             | all-MiniLM-L6-v2 local              | P0       |
| Vector-based field extraction | Query relevant chunks, not full doc | P0       |
| Metadata filtering            | Filter by doc_id, chunk_type, etc.  | P1       |

### Week 3-4: Scoring & Regeneration

| Task                     | Details                                   | Priority |
| ------------------------ | ----------------------------------------- | -------- |
| Field confidence scoring | Format validation + extraction confidence | P0       |
| Document-level scoring   | Weighted aggregate                        | P0       |
| Field regeneration       | Regenerate single field from chunks       | P0       |
| Section regeneration     | Regenerate all fields in section          | P1       |
| Card regeneration        | Full card re-extraction                   | P1       |

### Week 4-5: Caching & Model Routing

| Task                 | Details                                         | Priority |
| -------------------- | ----------------------------------------------- | -------- |
| Multi-layer cache    | Memory → Redis → DB → API                       | P0       |
| Rule-based extractor | Regex for dates, numbers, emails (free)         | P0       |
| Model router         | Small model for simple tasks, large for complex | P1       |
| Cost tracking        | Log API usage per user per day                  | P1       |
| PostgreSQL migration | Move from SQLite to PostgreSQL                  | P0       |

### Phase 2 Deliverables

- [ ] 60-80% reduction in API costs
- [ ] Confidence scores on all fields
- [ ] Field-level regeneration
- [ ] Redis caching layer
- [ ] Vector DB (ChromaDB) with semantic search
- [ ] Rule-based extraction for simple fields
- [ ] Cost tracking dashboard

---

## Phase 3 — Scaling (6-8 Weeks)

### Goal

Handle 10x traffic, async processing, horizontal scaling, advanced features.

| Week | Focus                | Tasks                                                                    |
| ---- | -------------------- | ------------------------------------------------------------------------ |
| 1-2  | **Async Pipeline**   | Celery workers, Redis queue, task routing, WebSocket progress            |
| 2-3  | **Advanced Scoring** | Cross-field validation, LLM uncertainty detection, recalculation on edit |
| 3-4  | **Version History**  | Edit tracking, diff computation, rollback capability                     |
| 4-5  | **Horizontal Scale** | Docker Compose multi-replica, Nginx load balancer, worker scaling        |
| 5-6  | **Monitoring**       | Prometheus metrics, Grafana dashboards, error alerting                   |
| 6-7  | **Performance**      | Connection pooling, query optimization, index tuning                     |
| 7-8  | **Testing**          | Load testing (Locust), integration tests, CI/CD pipeline                 |

### Phase 3 Deliverables

- [ ] Async pipeline with Celery + Redis
- [ ] WebSocket real-time progress
- [ ] Edit version history with diffs
- [ ] Horizontal scaling (2+ API instances, 2+ OCR workers)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Load tested to 100 concurrent users

---

## Phase 4 — Enterprise (8-12 Weeks)

### Goal

Multi-tenant SaaS, custom templates, admin dashboard, API access.

| Week  | Focus                   | Tasks                                                                 |
| ----- | ----------------------- | --------------------------------------------------------------------- |
| 1-2   | **Multi-tenant**        | Organization accounts, team management, data isolation                |
| 3-4   | **Custom Templates**    | Template builder UI, custom field types, template marketplace         |
| 5-6   | **Admin Dashboard**     | Usage analytics, cost monitoring, user management, audit logs         |
| 7-8   | **API Access**          | REST API for third-party integration, API keys, rate limiting per key |
| 9-10  | **Ollama Integration**  | Self-hosted LLM for cost reduction, model routing refinement          |
| 10-12 | **Enterprise Features** | SSO (SAML/OIDC), compliance (GDPR), data export, SLA                  |

### Phase 4 Deliverables

- [ ] Multi-tenant architecture
- [ ] Custom template builder
- [ ] Admin analytics dashboard
- [ ] Third-party API with documentation
- [ ] Self-hosted LLM option (Ollama)
- [ ] SSO integration
- [ ] GDPR compliance tools

---

## Risk Mitigation

| Risk                      | Impact          | Mitigation                                                |
| ------------------------- | --------------- | --------------------------------------------------------- |
| Gemini API price increase | High cost       | Phase 2: Hybrid OCR + caching. Phase 4: Ollama fallback   |
| Gemini API downtime       | Service outage  | Circuit breaker pattern, queue with retry                 |
| Large PDF memory issues   | Crashes         | Batch processing, memory limits per worker                |
| Bangla OCR quality        | Poor extraction | Fine-tune prompts, user feedback loop, confidence scoring |
| Database growth           | Slow queries    | Pagination, archival, partitioning (Phase 3)              |
| Security breach           | Data loss       | Encryption at rest, JWT rotation, audit logs              |
