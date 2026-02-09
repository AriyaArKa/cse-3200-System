# 4. Sequence Diagram

## Mermaid Files

| File | Description |
|------|-------------|
| [seq_document_upload.mmd](seq_document_upload.mmd) | Document Upload & Processing flow |
| [seq_summarization.mmd](seq_summarization.mmd) | Document Summarization flow |
| [seq_template_report.mmd](seq_template_report.mmd) | Template-Based Report Generation & Export |
| [seq_rag_query.mmd](seq_rag_query.mmd) | RAG Query (Question Answering) |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a Sequence Diagram?

A **Sequence Diagram** shows the **time-ordered interactions** between objects/components in the system. It illustrates the **message flow** between actors and system components for specific use cases, making it clear **who communicates with whom and in what order**.

## Why Use It?

- Shows **detailed message flow** between components
- Captures **timing and order** of operations
- Identifies **all interactions** for a specific scenario
- Helps in **API design** and **interface planning**
- Excellent for **documenting complex workflows**

## When to Use

- During **detailed design phase**
- When documenting **API interactions**
- For **complex multi-component workflows**
- When explaining **system behavior** to developers

---

## Sequence 1: Document Upload & Processing

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Gateway
    participant OCR as OCR Engine
    participant NLP as NLP Pipeline
    participant EMB as Embedding<br/>(Nomic)
    participant VDB as Vector DB
    participant FS as File Storage

    User->>UI: Select & Upload Document
    UI->>API: POST /upload (file)
    API->>FS: Store original file
    FS-->>API: file_id, file_path

    alt Document is Image/Scanned PDF
        API->>OCR: Process image
        OCR->>OCR: Bengali OCR
        OCR->>OCR: English OCR
        OCR-->>API: Extracted text
    else Document is Digital Text
        API->>API: Extract text directly
    end

    API->>NLP: Process bilingual text
    NLP->>NLP: Language detection
    NLP->>NLP: Tokenization
    NLP->>NLP: Text cleaning
    NLP-->>API: Processed text + metadata

    API->>NLP: Chunk text
    NLP-->>API: Text chunks[]

    loop For each chunk
        API->>EMB: Generate embedding
        EMB-->>API: Vector (768d)
        API->>VDB: Store (chunk, vector, metadata)
    end

    VDB-->>API: Confirmation
    API-->>UI: Upload success + document_id
    UI-->>User: Show success notification
```

---

## Sequence 2: Document Summarization

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Gateway
    participant RAG as RAG Engine
    participant VDB as Vector DB
    participant EMB as Embedding<br/>(Nomic)
    participant LLM as Mistral LLM<br/>(Ollama)

    User->>UI: Click "Summarize Document"
    UI->>API: POST /summarize {doc_id}

    API->>VDB: Fetch all chunks for doc_id
    VDB-->>API: Document chunks[]

    API->>RAG: Prepare context
    RAG->>EMB: Embed summary query
    EMB-->>RAG: Query vector

    RAG->>VDB: Similarity search
    VDB-->>RAG: Top-K relevant chunks

    RAG->>RAG: Build prompt with context
    RAG->>LLM: Generate summary
    
    Note over LLM: Mistral processes<br/>Bengali + English text

    LLM-->>RAG: Generated summary
    RAG-->>API: Summary text

    API-->>UI: {summary, metadata}
    UI-->>User: Display summary in editor

    opt User edits summary
        User->>UI: Make edits
        UI->>API: PUT /summary {edited_text}
        API-->>UI: Saved confirmation
    end
```

---

## Sequence 3: Template-Based Report Generation & Export

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Gateway
    participant TE as Template Engine
    participant LLM as Mistral LLM
    participant EXP as Export Engine

    User->>UI: Browse template cards
    UI->>API: GET /templates
    API-->>UI: Template list (10-15 cards)
    UI-->>User: Display template gallery

    User->>UI: Select template (e.g., "Meeting Minutes")
    UI->>API: POST /report {template_id, doc_id}

    API->>TE: Load template definition
    TE-->>API: Template schema + layout

    API->>LLM: Fill template with document data
    
    Note over LLM: Extract relevant info<br/>for template fields

    LLM-->>API: Structured data for template

    API->>TE: Render template with data
    TE-->>API: Formatted report (HTML)

    API-->>UI: Report preview
    UI-->>User: Show editable report

    User->>UI: Edit report content
    User->>UI: Click "Export as PDF"
    UI->>API: POST /export {format: "pdf", content}

    API->>EXP: Generate PDF
    EXP->>EXP: Render HTML to PDF
    EXP->>EXP: Apply Bengali fonts
    EXP-->>API: PDF file

    API-->>UI: Download link
    UI-->>User: Download PDF file
```

---

## Sequence 4: RAG Query (Question Answering)

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Gateway
    participant EMB as Nomic Embed
    participant VDB as Vector DB
    participant LLM as Mistral

    User->>UI: Ask question about document
    UI->>API: POST /query {question, doc_id}

    API->>EMB: Embed question
    EMB-->>API: Question vector

    API->>VDB: Similarity search (question_vector)
    VDB-->>API: Top 5 relevant chunks

    API->>API: Build RAG prompt
    Note over API: System: You are a bilingual assistant...<br/>Context: [relevant chunks]<br/>Question: [user question]

    API->>LLM: POST /api/generate
    LLM-->>API: Answer text

    API-->>UI: {answer, sources[]}
    UI-->>User: Display answer with source references
```

---

## Key Observations

| Aspect | Detail |
|--------|--------|
| **Async Operations** | Embedding generation for chunks happens in a loop |
| **Conditional Flow** | OCR is only used for scanned/image documents |
| **Optional Steps** | User editing is optional before export |
| **Local Processing** | All AI calls go to local Ollama instance (no external API) |
| **Multi-format** | Same workflow supports PDF, DOCX, and Excel export |
