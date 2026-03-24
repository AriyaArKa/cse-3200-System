# 13 — System Flowcharts

All diagrams use Mermaid syntax. Render in any Mermaid-compatible viewer (GitHub, VS Code extension, mermaid.live).

---

## 1. Master Pipeline Flow

```mermaid
flowchart TD
    A[📄 User Uploads PDF] --> B{File Valid?}
    B -->|No| B1[❌ Return Error]
    B -->|Yes| C{Duplicate Check<br/>SHA-256 Hash}
    C -->|Exists| C1[✅ Return Cached Result]
    C -->|New| D[💾 Save to Storage]
    D --> E[📋 Create DB Record<br/>Status: uploaded]
    E --> F[📨 Queue Async Pipeline]
    F --> G[🔄 Return 202 Accepted<br/>+ document_id]

    F --> H[ASYNC PIPELINE]

    H --> I[Step 2: PDF → Images<br/>+ Native Text Extract]
    I --> J{Native Text<br/>> 50 chars?}
    J -->|Yes| K[✅ Use Native Text<br/>Cost: $0]
    J -->|No| L{Cache Hit?<br/>Page Hash}
    L -->|Yes| M[✅ Use Cached OCR<br/>Cost: $0]
    L -->|No| N[🤖 Gemini 2.5 Flash OCR<br/>Cost: ~$0.015]
    N --> O[💾 Cache OCR Result]

    K --> P[Step 4: Semantic Chunking]
    M --> P
    O --> P

    P --> Q[Step 5: Generate Embeddings<br/>all-MiniLM-L6-v2 - FREE]
    Q --> R[💾 Store in ChromaDB]
    R --> S[Step 6: Classify Document Type]
    S --> T[Select Template Card]
    T --> U[Fill Card Fields<br/>Rule-based + LLM]
    U --> V[Step 7: Confidence Scoring]
    V --> W[💾 Save to PostgreSQL]
    W --> X[📡 WebSocket: Pipeline Complete]

    X --> Y{User Action}
    Y -->|View| Z[Display Card]
    Y -->|Edit| AA[Track Edit + Re-score]
    Y -->|Regenerate| AB[Regen Field/Section/Card]
    Y -->|Download| AC[Export JSON]

    AB --> AD{Regen Scope}
    AD -->|Field| AE[Query 3 Chunks<br/>Small Prompt]
    AD -->|Section| AF[Query Section Chunks<br/>Medium Prompt]
    AD -->|Card| AG[Query All Chunks<br/>Full Regen]

    AE --> V
    AF --> V
    AG --> V

    style A fill:#4CAF50,color:#fff
    style B1 fill:#f44336,color:#fff
    style C1 fill:#2196F3,color:#fff
    style K fill:#4CAF50,color:#fff
    style M fill:#2196F3,color:#fff
    style N fill:#FF9800,color:#fff
    style X fill:#4CAF50,color:#fff
```

---

## 2. OCR Decision Tree

```mermaid
flowchart TD
    A[PDF Page] --> B[Extract Native Text<br/>PyMuPDF - FREE]
    B --> C{Text Length<br/>> 50 chars?}

    C -->|Yes| D[✅ Native Text]
    D --> D1[Confidence: 0.95]
    D --> D2[Cost: $0.00]
    D --> D3{Has Tables?}
    D3 -->|Yes| D4[pdfplumber<br/>Table Extract]
    D3 -->|No| E[→ Chunking]
    D4 --> E

    C -->|No| F[Compute Page Hash<br/>SHA-256 of pixels]
    F --> G{Redis Cache<br/>Hit?}

    G -->|Yes| H[✅ Cached Result]
    H --> H1[Confidence: 0.90]
    H --> H2[Cost: $0.00]
    H --> E

    G -->|No| I[Select DPI]
    I --> I1{Content Type}
    I1 -->|Clean Text| I2[DPI: 150]
    I1 -->|Mixed| I3[DPI: 200]
    I1 -->|Handwritten/Low-Q| I4[DPI: 300]

    I2 --> J[Convert to Image]
    I3 --> J
    I4 --> J

    J --> K[🤖 Gemini 2.5 Flash<br/>OCR API Call]
    K --> K1[Confidence: 0.85]
    K --> K2[Cost: ~$0.015]
    K --> L[💾 Cache Result<br/>TTL: 30 days]
    L --> E

    style D fill:#4CAF50,color:#fff
    style H fill:#2196F3,color:#fff
    style K fill:#FF9800,color:#fff
```

---

## 3. Chunking Pipeline

```mermaid
flowchart TD
    A[OCR Text Output] --> B[Detect Sections]

    B --> C{Section Type?}
    C -->|Header| D[Header Chunk]
    C -->|Paragraph| E[Paragraph Chunk]
    C -->|Table| F[Table Chunk]
    C -->|List| G[List Chunk]
    C -->|Empty Line| H[Section Break]

    D --> I{Token Count<br/>> 512?}
    E --> I
    F --> I
    G --> I

    I -->|No| J[Single Chunk<br/>+ Metadata]
    I -->|Yes| K[Split with 64-token<br/>Overlap]
    K --> L[Sub-chunk 1]
    K --> M[Sub-chunk 2]
    K --> N[Sub-chunk N]

    J --> O[Add Metadata]
    L --> O
    M --> O
    N --> O

    O --> P{Metadata Enrichment}
    P --> P1[has_bangla?]
    P --> P2[has_table?]
    P --> P3[has_dates?]
    P --> P4[token_count]
    P --> P5[chunk_type]
    P --> P6[page_number]

    P1 --> Q[Generate Embedding<br/>all-MiniLM-L6-v2]
    P2 --> Q
    P3 --> Q
    P4 --> Q
    P5 --> Q
    P6 --> Q

    Q --> R[Store in ChromaDB<br/>+ PostgreSQL]

    style J fill:#4CAF50,color:#fff
    style K fill:#FF9800,color:#fff
    style R fill:#2196F3,color:#fff
```

---

## 4. Template Card Generation Flow

```mermaid
flowchart TD
    A[Document Classified] --> B{Document Type}

    B -->|University Notice| C[Student Support Card]
    B -->|Job Circular| D[Job Eligibility Card]
    B -->|Govt Circular| E[Govt Policy Card]
    B -->|Financial Doc| F[Financial Health Card]
    B -->|Meeting Doc| G[Meeting Tracker Card]

    C --> H[Load Template Sections]
    D --> H
    E --> H
    F --> H
    G --> H

    H --> I[For Each Field]

    I --> J{Field Type?}

    J -->|date, email, phone| K[Rule-Based Extract<br/>Regex - $0]
    J -->|text, list| L[Vector Search<br/>Top 3 Chunks]
    J -->|ai_summary, ai_warning| M[Vector Search<br/>+ LLM Generate]
    J -->|table| N[Table Extraction<br/>pdfplumber + LLM]
    J -->|checklist| O[LLM Analysis<br/>from Context]

    K --> P[Fill Field Value]
    L --> Q[Small LLM Prompt<br/>~$0.001]
    Q --> P
    M --> R[Full LLM Prompt<br/>~$0.005]
    R --> P
    N --> P
    O --> R

    P --> S[Score Field<br/>0.0 - 1.0]
    S --> T{Confidence<br/>> 0.7?}
    T -->|Yes| U[✅ Auto-accept]
    T -->|No| V[⚠️ Flag for Review]

    U --> W[All Fields Done?]
    V --> W
    W -->|No| I
    W -->|Yes| X[Calculate Doc Score]
    X --> Y[💾 Save Card]
    Y --> Z[📡 Notify User]

    style K fill:#4CAF50,color:#fff
    style Q fill:#FF9800,color:#fff
    style R fill:#f44336,color:#fff
    style U fill:#4CAF50,color:#fff
    style V fill:#FF9800,color:#fff
```

---

## 5. Regeneration Workflow

```mermaid
flowchart TD
    A[User Clicks Regenerate] --> B{Scope?}

    B -->|Single Field| C[Get Field Config]
    B -->|Section| D[Get All Section Fields]
    B -->|Full Card| E[Get All Card Fields]

    C --> F[Build Field Query<br/>field_id → search terms]
    D --> F1[Build Section Query]
    E --> F2[Get All Document Chunks]

    F --> G[Vector DB: Top 3 Chunks<br/>Filtered by document_id]
    F1 --> G1[Vector DB: Top 5 Chunks<br/>per field in section]
    F2 --> G2[All Chunks for Document]

    G --> H[Build Minimal Prompt<br/>~200 tokens context]
    G1 --> H1[Build Section Prompt<br/>~500 tokens context]
    G2 --> H2[Build Full Card Prompt<br/>~1000 tokens context]

    H --> I[Select Model<br/>Cheapest capable]
    H1 --> I
    H2 --> I1[Use Gemini 2.5 Flash]

    I --> J[Generate New Value]
    I1 --> J

    J --> K[Save Version History]
    K --> L[old_value → version log]
    K --> M[new_value → current]
    K --> N[source: ai_regeneration]

    M --> O[Re-score Field]
    O --> P[Re-score Document]
    P --> Q[Update ChromaDB<br/>if >30% changed]
    Q --> R[📡 WebSocket Update<br/>to Frontend]

    style G fill:#2196F3,color:#fff
    style H fill:#4CAF50,color:#fff
    style H2 fill:#FF9800,color:#fff
    style R fill:#4CAF50,color:#fff
```

---

## 6. Confidence Scoring Flow

```mermaid
flowchart TD
    A[Extracted Field Value] --> B[Component Scores]

    B --> C[OCR Confidence<br/>Weight: 0.25]
    B --> D[Extraction Confidence<br/>Weight: 0.35]
    B --> E[Format Validation<br/>Weight: 0.25]
    B --> F[Cross-Reference<br/>Weight: 0.15]

    C --> C1{OCR Method?}
    C1 -->|Native| C2[0.95]
    C1 -->|Cached| C3[0.90]
    C1 -->|Gemini| C4[0.85]
    C1 -->|User Edit| C5[1.00]

    D --> D1{Value in Source?}
    D1 -->|Exact Match| D2[1.00]
    D1 -->|Fuzzy Match| D3[0.60-0.90]
    D1 -->|Not Found| D4[0.00-0.30]

    E --> E1{Format Valid?}
    E1 -->|date matches pattern| E2[1.00]
    E1 -->|partial match| E3[0.50]
    E1 -->|invalid format| E4[0.10-0.30]

    F --> F1{Cross-check?}
    F1 -->|Dates consistent| F2[1.00]
    F1 -->|Dates conflict| F3[0.30]
    F1 -->|No cross-ref| F4[0.80]

    C2 --> G[Weighted Sum]
    C3 --> G
    C4 --> G
    C5 --> G
    D2 --> G
    D3 --> G
    D4 --> G
    E2 --> G
    E3 --> G
    E4 --> G
    F2 --> G
    F3 --> G
    F4 --> G

    G --> H{Final Score}
    H -->|>= 0.9| I[✅ Excellent<br/>Green Badge]
    H -->|>= 0.7| J[🔵 Good<br/>Blue Badge]
    H -->|>= 0.5| K[⚠️ Needs Review<br/>Yellow Badge]
    H -->|< 0.5| L[❌ Poor<br/>Red Badge]

    style I fill:#4CAF50,color:#fff
    style J fill:#2196F3,color:#fff
    style K fill:#FF9800,color:#fff
    style L fill:#f44336,color:#fff
```

---

## 7. Caching Architecture

```mermaid
flowchart TD
    A[Request] --> B{L1: In-Memory<br/>LRU Cache}

    B -->|HIT| C[Return<br/>< 1ms]
    B -->|MISS| D{L2: Redis<br/>TTL: 30 days}

    D -->|HIT| E[Promote to L1]
    E --> F[Return<br/>~1ms]
    D -->|MISS| G{L3: PostgreSQL<br/>Permanent}

    G -->|HIT| H[Promote to L2 + L1]
    H --> I[Return<br/>~5ms]
    G -->|MISS| J[L4: API Call<br/>Gemini / LLM]

    J --> K[Store in L3]
    K --> L[Store in L2]
    L --> M[Store in L1]
    M --> N[Return<br/>2-5 seconds]

    style C fill:#4CAF50,color:#fff
    style F fill:#2196F3,color:#fff
    style I fill:#FF9800,color:#fff
    style N fill:#f44336,color:#fff
```

---

## 8. User Edit & Version Tracking

```mermaid
flowchart TD
    A[User Edits Field Value] --> B[Frontend sends<br/>PATCH /api/v1/cards/id/fields/field_id]

    B --> C[Backend receives edit]
    C --> D[Create Version Record]
    D --> D1[old_value]
    D --> D2[new_value]
    D --> D3[source: user_edit]
    D --> D4[timestamp]
    D --> D5[user_id]

    D --> E[Compute Diff]
    E --> E1[similarity_ratio]
    E --> E2[added lines]
    E --> E3[removed lines]

    E --> F{Significant Change?<br/>>30% different}
    F -->|Yes| G[Re-embed Chunk<br/>in ChromaDB]
    F -->|No| H[Skip re-embedding]

    G --> I[Re-score Field]
    H --> I

    I --> J[Set source_type =<br/>user_edit]
    J --> K[Set confidence = 1.0<br/>User verified]
    K --> L[Re-score Document]
    L --> M[💾 Save All Changes]
    M --> N[📡 Return Updated Card]

    style A fill:#4CAF50,color:#fff
    style G fill:#FF9800,color:#fff
    style K fill:#2196F3,color:#fff
```

---

## 9. Model Routing Decision

```mermaid
flowchart TD
    A[Incoming Task] --> B{Task Type?}

    B -->|Extract Date| C[Regex Pattern<br/>$0.00]
    B -->|Extract Email| C
    B -->|Extract Phone| C
    B -->|Extract Number| C

    B -->|Classify Doc Type| D[Gemini 2.0 Flash-Lite<br/>~$0.001]
    B -->|Simple Summary| D
    B -->|Fill Simple Field| D

    B -->|OCR Scanned Page| E[Gemini 2.5 Flash<br/>~$0.015]
    B -->|Complex Analysis| E
    B -->|Bangla Processing| E
    B -->|Full Card Regen| E

    B -->|Summarization| F{Phase 3+?}
    F -->|Yes| G[Ollama + Llama 3.1<br/>$0.00 - Local]
    F -->|No| D

    C --> H[Return Result]
    D --> H
    E --> H
    G --> H

    style C fill:#4CAF50,color:#fff
    style D fill:#2196F3,color:#fff
    style E fill:#FF9800,color:#fff
    style G fill:#4CAF50,color:#fff
```

---

## 10. Deployment Architecture

```mermaid
flowchart TD
    subgraph Internet
        U[Users]
    end

    subgraph "Load Balancer"
        LB[Nginx]
    end

    subgraph "Application Tier"
        API1[FastAPI Instance 1]
        API2[FastAPI Instance 2]
        WS[WebSocket Server]
    end

    subgraph "Worker Tier"
        W1[OCR Worker 1]
        W2[OCR Worker 2]
        W3[Embed Worker]
        W4[Score Worker]
    end

    subgraph "Data Tier"
        PG[(PostgreSQL)]
        PG_R[(PG Read Replica)]
        RD[(Redis)]
        CH[(ChromaDB)]
        S3[(MinIO / S3)]
    end

    U --> LB
    LB --> API1
    LB --> API2
    LB --> WS

    API1 --> RD
    API2 --> RD
    API1 --> PG
    API2 --> PG_R
    WS --> RD

    RD --> W1
    RD --> W2
    RD --> W3
    RD --> W4

    W1 --> PG
    W2 --> PG
    W3 --> CH
    W4 --> PG

    W1 --> S3
    W2 --> S3
    API1 --> S3
```

---

## 11. Database Entity Relationship

```mermaid
erDiagram
    USERS ||--o{ DOCUMENTS : uploads
    USERS ||--o{ TEMPLATE_CARDS : owns
    USERS ||--o{ EDIT_HISTORY : makes

    DOCUMENTS ||--o{ PAGES : contains
    DOCUMENTS ||--o{ CHUNKS : has
    DOCUMENTS ||--o{ TEMPLATE_CARDS : generates

    PAGES ||--|| OCR_RESULTS : produces
    PAGES ||--o{ CHUNKS : splits_into

    CHUNKS ||--|| EMBEDDINGS : has

    TEMPLATE_CARDS ||--o{ CARD_FIELDS : contains

    CARD_FIELDS ||--o{ EDIT_HISTORY : tracks
    CARD_FIELDS ||--o{ REGENERATION_LOGS : logs

    USERS {
        uuid id PK
        string email
        string password_hash
        string role
        int api_quota_daily
    }

    DOCUMENTS {
        uuid id PK
        uuid user_id FK
        string original_filename
        string file_hash
        int total_pages
        string status
        string detected_type
        float document_score
    }

    PAGES {
        uuid id PK
        uuid document_id FK
        int page_number
        string image_path
        string image_hash
        string ocr_method
    }

    OCR_RESULTS {
        uuid id PK
        uuid page_id FK
        text raw_text
        jsonb structured_json
        string ocr_method
        float ocr_confidence
        decimal api_cost_usd
    }

    CHUNKS {
        uuid id PK
        uuid document_id FK
        uuid page_id FK
        text content
        string chunk_type
        int token_count
        int level
        uuid parent_chunk_id
    }

    EMBEDDINGS {
        uuid id PK
        uuid chunk_id FK
        string model_name
        int dimensions
        bytea vector
    }

    TEMPLATE_CARDS {
        uuid id PK
        uuid document_id FK
        uuid user_id FK
        string template_id
        string status
        float card_score
    }

    CARD_FIELDS {
        uuid id PK
        uuid card_id FK
        string field_id
        string field_type
        text current_value
        float confidence_score
        string source_type
    }

    EDIT_HISTORY {
        uuid id PK
        uuid card_id FK
        string field_id
        uuid user_id FK
        text old_value
        text new_value
        string edit_source
    }

    REGENERATION_LOGS {
        uuid id PK
        uuid card_id FK
        string regen_type
        string field_id
        string model_used
        decimal api_cost_usd
    }
```

---

## How to Render These Diagrams

1. **VS Code:** Install "Markdown Preview Mermaid Support" extension
2. **GitHub:** Mermaid renders natively in `.md` files
3. **Online:** Paste code at [mermaid.live](https://mermaid.live)
4. **Export as PNG:** Use mermaid CLI: `npx @mermaid-js/mermaid-cli mmdc -i input.md -o output.png`
