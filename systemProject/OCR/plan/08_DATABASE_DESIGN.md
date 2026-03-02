# 08 — Database Design

## Entity Relationship Diagram

```
┌──────────┐     ┌────────────┐     ┌──────────┐     ┌─────────────┐
│  Users   │────<│ Documents  │────<│  Pages   │────<│ OCR Results │
└──────────┘  1:N└────────────┘  1:N└──────────┘  1:1└─────────────┘
                       │                  │
                       │ 1:N              │ 1:N
                       ▼                  ▼
                ┌──────────────┐   ┌──────────┐     ┌────────────┐
                │Template Cards│   │ Chunks   │────<│ Embeddings │
                └──────────────┘   └──────────┘  1:1└────────────┘
                       │
                       │ 1:N
                       ▼
                ┌──────────────┐
                │ Card Fields  │
                └──────────────┘
                       │
               ┌───────┼───────┐
               │ 1:N   │       │ 1:N
               ▼       │       ▼
        ┌────────────┐ │ ┌──────────────┐
        │Edit History│ │ │ Regen Logs   │
        └────────────┘ │ └──────────────┘
                       │ 1:N
                       ▼
                ┌──────────────┐
                │Field Versions│
                └──────────────┘
```

---

## Full Schema (PostgreSQL)

### 1. Users

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(50) DEFAULT 'user',  -- 'user', 'admin'
    api_quota_daily INT DEFAULT 100,              -- Rate limiting
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

### 2. Documents

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- File metadata
    original_filename VARCHAR(500) NOT NULL,
    file_hash       VARCHAR(64) NOT NULL,         -- SHA-256 of file bytes (dedup)
    file_size_bytes BIGINT NOT NULL,
    mime_type       VARCHAR(100) DEFAULT 'application/pdf',
    storage_path    VARCHAR(1000) NOT NULL,        -- Path in MinIO/S3/local

    -- Processing metadata
    total_pages     INT,
    status          VARCHAR(50) DEFAULT 'uploaded',
    -- Status flow: uploaded → processing → ocr_complete → cards_generated → completed → failed

    -- Classification
    detected_type   VARCHAR(100),                  -- "University Notice", "Job Circular", etc.
    type_confidence FLOAT,
    language        VARCHAR(10) DEFAULT 'bn',      -- Primary language detected

    -- Scoring
    document_score  FLOAT,                         -- Aggregate confidence (0.0 - 1.0)

    -- Timestamps
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_user_file UNIQUE(user_id, file_hash)  -- Prevent same user uploading same file
);

CREATE INDEX idx_docs_user ON documents(user_id);
CREATE INDEX idx_docs_status ON documents(status);
CREATE INDEX idx_docs_hash ON documents(file_hash);
CREATE INDEX idx_docs_type ON documents(detected_type);
```

### 3. Pages

```sql
CREATE TABLE pages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number     INT NOT NULL,

    -- Image metadata
    image_path      VARCHAR(1000),                 -- Storage path of converted image
    image_hash      VARCHAR(64),                   -- SHA-256 for deduplication
    dpi             INT DEFAULT 300,
    width_px        INT,
    height_px       INT,

    -- Processing
    ocr_method      VARCHAR(50),                   -- 'native', 'gemini', 'cached'
    has_native_text BOOLEAN DEFAULT FALSE,
    native_text_length INT DEFAULT 0,

    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_doc_page UNIQUE(document_id, page_number)
);

CREATE INDEX idx_pages_doc ON pages(document_id);
CREATE INDEX idx_pages_hash ON pages(image_hash);
```

### 4. OCR Results

```sql
CREATE TABLE ocr_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- OCR output
    raw_text        TEXT,                           -- Raw OCR text
    structured_json JSONB,                         -- Structured extraction result

    -- Method & quality
    ocr_method      VARCHAR(50) NOT NULL,          -- 'native', 'gemini_2.5_flash', 'cached'
    model_used      VARCHAR(100),
    ocr_confidence  FLOAT,                         -- Overall page OCR confidence

    -- Cost tracking
    input_tokens    INT,
    output_tokens   INT,
    api_cost_usd    DECIMAL(10,6),

    -- Caching
    cache_key       VARCHAR(64),                   -- Page hash for caching
    cached_at       TIMESTAMPTZ,

    processing_time_ms INT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_page_ocr UNIQUE(page_id)        -- One OCR result per page
);

CREATE INDEX idx_ocr_doc ON ocr_results(document_id);
CREATE INDEX idx_ocr_cache ON ocr_results(cache_key);
```

### 5. Chunks

```sql
CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id         UUID REFERENCES pages(id) ON DELETE SET NULL,

    -- Content
    content         TEXT NOT NULL,
    chunk_type      VARCHAR(50) NOT NULL,          -- 'header', 'paragraph', 'table', 'list'

    -- Position
    chunk_index     INT NOT NULL,                  -- Order within document
    page_number     INT,
    start_position  INT,                           -- Character offset in page text
    end_position    INT,

    -- Hierarchy
    level           INT DEFAULT 2,                 -- 0=doc, 1=page, 2=section
    parent_chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,

    -- Metadata
    token_count     INT,
    has_bangla      BOOLEAN DEFAULT FALSE,
    has_table       BOOLEAN DEFAULT FALSE,
    has_dates       BOOLEAN DEFAULT FALSE,
    detected_dates  JSONB,                         -- Array of date strings
    detected_entities JSONB,                       -- Array of entity strings

    -- Source quality
    ocr_method      VARCHAR(50),
    ocr_confidence  FLOAT,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_doc ON chunks(document_id);
CREATE INDEX idx_chunks_page ON chunks(page_id);
CREATE INDEX idx_chunks_type ON chunks(chunk_type);
CREATE INDEX idx_chunks_level ON chunks(level);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);
```

### 6. Embeddings

```sql
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,

    -- Embedding data
    model_name      VARCHAR(100) NOT NULL,         -- 'all-MiniLM-L6-v2'
    dimensions      INT NOT NULL,                  -- 384
    vector          BYTEA NOT NULL,                -- Binary embedding (stored in PG, indexed in ChromaDB)

    -- ChromaDB reference
    chromadb_id     VARCHAR(100),                  -- ID in ChromaDB collection

    -- Versioning
    version         INT DEFAULT 1,                 -- Incremented on re-embedding

    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_chunk_embed UNIQUE(chunk_id, model_name)
);

CREATE INDEX idx_embed_chunk ON embeddings(chunk_id);
```

### 7. Template Cards

```sql
CREATE TABLE template_cards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Template
    template_id     VARCHAR(100) NOT NULL,         -- 'student_support_card'
    template_name   VARCHAR(255),                  -- 'Student Action & Support Card'

    -- Status
    status          VARCHAR(50) DEFAULT 'draft',
    -- Status: draft → auto_filled → reviewed → finalized

    -- Scoring
    card_score      FLOAT,                         -- Aggregate of all field scores
    total_fields    INT,
    filled_fields   INT,
    low_confidence_fields INT,

    -- Metadata
    auto_matched    BOOLEAN DEFAULT TRUE,          -- Was template auto-selected?

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cards_doc ON template_cards(document_id);
CREATE INDEX idx_cards_user ON template_cards(user_id);
CREATE INDEX idx_cards_template ON template_cards(template_id);
CREATE INDEX idx_cards_status ON template_cards(status);
```

### 8. Card Fields

```sql
CREATE TABLE card_fields (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id         UUID NOT NULL REFERENCES template_cards(id) ON DELETE CASCADE,

    -- Field definition
    field_id        VARCHAR(100) NOT NULL,          -- 'notice_title', 'issue_date'
    field_type      VARCHAR(50) NOT NULL,           -- 'text', 'date', 'list', 'table', etc.
    section_id      VARCHAR(100),                   -- Which section in template

    -- Value
    current_value   TEXT,                           -- Current field value
    display_value   TEXT,                           -- Formatted for display

    -- Source tracking
    source_type     VARCHAR(50) DEFAULT 'ai_extraction',
    -- 'ai_extraction', 'ai_regeneration', 'user_edit', 'rule_based'
    source_chunk_ids JSONB,                        -- Array of chunk IDs used for extraction

    -- Scoring
    confidence_score FLOAT,
    ocr_score       FLOAT,
    extraction_score FLOAT,
    validation_score FLOAT,
    cross_ref_score FLOAT,
    needs_review    BOOLEAN DEFAULT FALSE,

    -- Config
    is_editable     BOOLEAN DEFAULT TRUE,
    is_regeneratable BOOLEAN DEFAULT FALSE,

    -- Version tracking
    version_count   INT DEFAULT 1,
    last_edited_by  VARCHAR(50),                   -- 'ai' or 'user'

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_card_field UNIQUE(card_id, field_id)
);

CREATE INDEX idx_fields_card ON card_fields(card_id);
CREATE INDEX idx_fields_section ON card_fields(section_id);
CREATE INDEX idx_fields_confidence ON card_fields(confidence_score);
CREATE INDEX idx_fields_review ON card_fields(needs_review) WHERE needs_review = TRUE;
```

### 9. Edit History

```sql
CREATE TABLE edit_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id         UUID NOT NULL REFERENCES template_cards(id) ON DELETE CASCADE,
    field_id        VARCHAR(100) NOT NULL,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Change
    old_value       TEXT,
    new_value       TEXT NOT NULL,

    -- Metadata
    edit_source     VARCHAR(50) NOT NULL,           -- 'user_edit', 'ai_regeneration', 'ai_extraction'
    model_used      VARCHAR(100),                   -- Which model if AI
    prompt_used     TEXT,                            -- Stored for reproducibility

    -- Diff
    similarity_ratio FLOAT,                         -- How much changed (0-1)

    -- Scoring (at time of edit)
    confidence_before FLOAT,
    confidence_after  FLOAT,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_edits_card ON edit_history(card_id);
CREATE INDEX idx_edits_field ON edit_history(card_id, field_id);
CREATE INDEX idx_edits_user ON edit_history(user_id);
CREATE INDEX idx_edits_source ON edit_history(edit_source);
CREATE INDEX idx_edits_time ON edit_history(created_at);
```

### 10. Regeneration Logs

```sql
CREATE TABLE regeneration_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id         UUID NOT NULL REFERENCES template_cards(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id),

    -- Scope
    regen_type      VARCHAR(50) NOT NULL,           -- 'field', 'section', 'card'
    field_id        VARCHAR(100),                    -- NULL for card-level regen
    section_id      VARCHAR(100),                    -- NULL for field-level regen

    -- Execution
    model_used      VARCHAR(100) NOT NULL,
    prompt_tokens   INT,
    completion_tokens INT,
    api_cost_usd    DECIMAL(10,6),
    processing_time_ms INT,

    -- Context used
    chunks_used     JSONB,                          -- Array of chunk_ids used as context
    context_token_count INT,

    -- Result
    status          VARCHAR(50) DEFAULT 'success',  -- 'success', 'failed', 'partial'
    error_message   TEXT,

    -- User guidance
    user_hint       TEXT,                            -- Optional user-provided hint

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_regen_card ON regeneration_logs(card_id);
CREATE INDEX idx_regen_type ON regeneration_logs(regen_type);
CREATE INDEX idx_regen_time ON regeneration_logs(created_at);
```

---

## Additional Tables

### API Usage Tracking (Cost Control)

```sql
CREATE TABLE api_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),

    -- API details
    api_provider    VARCHAR(50) NOT NULL,            -- 'gemini', 'ollama'
    model_name      VARCHAR(100) NOT NULL,
    operation_type  VARCHAR(50) NOT NULL,            -- 'ocr', 'extraction', 'regeneration'

    -- Tokens
    input_tokens    INT DEFAULT 0,
    output_tokens   INT DEFAULT 0,
    total_tokens    INT DEFAULT 0,

    -- Cost
    cost_usd        DECIMAL(10,6) DEFAULT 0,

    -- Reference
    document_id     UUID REFERENCES documents(id),
    card_id         UUID REFERENCES template_cards(id),

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_usage_user ON api_usage(user_id);
CREATE INDEX idx_usage_date ON api_usage(created_at);
CREATE INDEX idx_usage_type ON api_usage(operation_type);

-- Daily cost view
CREATE VIEW daily_user_cost AS
SELECT
    user_id,
    DATE(created_at) as usage_date,
    SUM(cost_usd) as total_cost,
    COUNT(*) as total_calls,
    SUM(total_tokens) as total_tokens
FROM api_usage
GROUP BY user_id, DATE(created_at);
```

### Processing Queue (for tracking async jobs)

```sql
CREATE TABLE processing_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id),
    user_id         UUID NOT NULL REFERENCES users(id),

    job_type        VARCHAR(50) NOT NULL,            -- 'full_pipeline', 'regenerate_field', etc.
    status          VARCHAR(50) DEFAULT 'queued',
    -- Status: queued → processing → completed → failed

    -- Progress
    total_steps     INT DEFAULT 0,
    completed_steps INT DEFAULT 0,
    current_step    VARCHAR(100),                    -- e.g., "OCR page 3/10"

    -- Error handling
    error_message   TEXT,
    retry_count     INT DEFAULT 0,
    max_retries     INT DEFAULT 3,

    -- Timing
    queued_at       TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    -- Result
    result_data     JSONB
);

CREATE INDEX idx_jobs_doc ON processing_jobs(document_id);
CREATE INDEX idx_jobs_status ON processing_jobs(status);
CREATE INDEX idx_jobs_user ON processing_jobs(user_id);
```

---

## Migration Strategy

```python
# Using Alembic (SQLAlchemy migration tool)
# alembic init migrations
# alembic revision --autogenerate -m "initial schema"
# alembic upgrade head

# MVP: Start with SQLite for development
SQLALCHEMY_URL = "sqlite:///./docint.db"

# Production: Switch to PostgreSQL
SQLALCHEMY_URL = "postgresql://user:pass@localhost:5432/docint"
```
