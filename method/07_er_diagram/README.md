# 7. ER Diagram (Entity-Relationship Diagram)

## Mermaid Files

| File                             | Description                          |
| -------------------------------- | ------------------------------------ |
| [er_diagram.mmd](er_diagram.mmd) | Complete Entity-Relationship Diagram |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is an ER Diagram?

An **Entity-Relationship (ER) Diagram** shows the **data entities** in the system, their **attributes**, and the **relationships** between them. It is the foundation for **database design** and shows how data is structured and connected.

## Why Use It?

- Defines the **data model** of the system
- Shows **entities, attributes, and relationships**
- Foundation for **database schema design**
- Identifies **primary keys, foreign keys, cardinality**
- Required for **any data-driven application**

## When to Use

- During **database design phase**
- When planning **data storage structure**
- For **normalizing** data models
- In **project documentation and reports**

---

## Complete ER Diagram

```mermaid
erDiagram
    USER {
        int user_id PK
        string username
        string email
        string password_hash
        string role
        datetime created_at
        datetime last_login
    }

    DOCUMENT {
        int document_id PK
        int user_id FK
        string file_name
        string file_path
        string file_type
        float file_size_mb
        string original_language
        text extracted_text
        string status
        datetime uploaded_at
        datetime processed_at
    }

    DOCUMENT_CHUNK {
        int chunk_id PK
        int document_id FK
        int chunk_index
        text chunk_text
        string language_tag
        string vector_id
        int token_count
    }

    EMBEDDING {
        int embedding_id PK
        int chunk_id FK
        string model_name
        int dimensions
        blob vector_data
        datetime created_at
    }

    TEMPLATE {
        int template_id PK
        string template_name
        string category
        text description
        json schema_definition
        text html_layout
        string language_support
        boolean is_active
        datetime created_at
    }

    REPORT {
        int report_id PK
        int user_id FK
        int document_id FK
        int template_id FK
        string report_title
        text content_html
        text content_json
        string status
        datetime created_at
        datetime last_modified
    }

    SUMMARY {
        int summary_id PK
        int document_id FK
        int user_id FK
        text summary_text
        string summary_type
        string model_used
        float processing_time
        datetime created_at
    }

    EXPORT_HISTORY {
        int export_id PK
        int report_id FK
        int user_id FK
        string export_format
        string file_path
        float file_size_mb
        datetime exported_at
    }

    QUERY_LOG {
        int query_id PK
        int user_id FK
        int document_id FK
        text query_text
        text response_text
        int chunks_retrieved
        float response_time
        datetime queried_at
    }

    TEMPLATE_CATEGORY {
        int category_id PK
        string category_name
        text description
        string icon
        int display_order
    }

    USER ||--o{ DOCUMENT : "uploads"
    USER ||--o{ REPORT : "creates"
    USER ||--o{ SUMMARY : "requests"
    USER ||--o{ EXPORT_HISTORY : "exports"
    USER ||--o{ QUERY_LOG : "queries"

    DOCUMENT ||--o{ DOCUMENT_CHUNK : "split into"
    DOCUMENT ||--o{ SUMMARY : "summarized as"
    DOCUMENT ||--o{ REPORT : "used in"
    DOCUMENT ||--o{ QUERY_LOG : "queried about"

    DOCUMENT_CHUNK ||--|| EMBEDDING : "has"

    TEMPLATE ||--o{ REPORT : "generates"
    TEMPLATE_CATEGORY ||--o{ TEMPLATE : "contains"

    REPORT ||--o{ EXPORT_HISTORY : "exported as"
```

---

## Entity Descriptions

| Entity                | Description                      | Records           |
| --------------------- | -------------------------------- | ----------------- |
| **USER**              | System users (officials, admins) | Hundreds          |
| **DOCUMENT**          | Uploaded bilingual documents     | Thousands         |
| **DOCUMENT_CHUNK**    | Text segments for RAG            | Tens of thousands |
| **EMBEDDING**         | Vector representations           | Tens of thousands |
| **TEMPLATE**          | Pre-defined card templates       | 10-15             |
| **REPORT**            | Generated formatted reports      | Thousands         |
| **SUMMARY**           | AI-generated summaries           | Thousands         |
| **EXPORT_HISTORY**    | Export audit trail               | Thousands         |
| **QUERY_LOG**         | User question history            | Thousands         |
| **TEMPLATE_CATEGORY** | Template groupings               | 4-5               |

---

## Relationship Summary

| Relationship        | Type | Description                              |
| ------------------- | ---- | ---------------------------------------- |
| User → Document     | 1:N  | One user uploads many documents          |
| Document → Chunk    | 1:N  | One document splits into many chunks     |
| Chunk → Embedding   | 1:1  | Each chunk has one embedding vector      |
| Template → Report   | 1:N  | One template generates many reports      |
| Category → Template | 1:N  | One category has many templates          |
| Document → Summary  | 1:N  | One document can have multiple summaries |
| Report → Export     | 1:N  | One report exported in multiple formats  |

---

## Template Categories (Pre-defined)

| Category ID | Name             | Templates                                                 |
| ----------- | ---------------- | --------------------------------------------------------- |
| 1           | Legal/Government | Affidavit, Notice, Application Form, Court Order          |
| 2           | Administrative   | Meeting Minutes, Internal Memo, Official Letter, Circular |
| 3           | Analytical       | Statistical Summary, Progress Report, Budget Report       |
| 4           | Summary Cards    | Executive Brief, Highlight Card, Quick Summary            |

---

## SQL Schema Preview

```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_type VARCHAR(20),
    extracted_text TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE document_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(document_id),
    chunk_index INTEGER,
    chunk_text TEXT NOT NULL,
    language_tag VARCHAR(10),
    vector_id VARCHAR(100)
);

CREATE TABLE templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name VARCHAR(200) NOT NULL,
    category VARCHAR(50),
    schema_definition JSON,
    html_layout TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
```
