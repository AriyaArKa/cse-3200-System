# 2. Data Flow Diagram (DFD)

## Mermaid Files

| File | Description |
|------|-------------|
| [dfd_level0_context.mmd](dfd_level0_context.mmd) | Level 0 — Context Diagram |
| [dfd_level1_processes.mmd](dfd_level1_processes.mmd) | Level 1 — Major Process Breakdown |
| [dfd_level2_ingestion.mmd](dfd_level2_ingestion.mmd) | Level 2 — Document Ingestion Detail |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a Data Flow Diagram?

A **Data Flow Diagram (DFD)** shows how data moves through the system — from input sources, through processing stages, to outputs. It focuses on **what data flows where**, not on control logic or timing.

DFDs have multiple levels:
- **Level 0 (Context Diagram)**: Shows the system as a single process with external entities
- **Level 1**: Breaks the system into major sub-processes
- **Level 2**: Further decomposes each sub-process

## Why Use It?

- Visualizes the **flow of data** through the system
- Identifies **data sources and destinations**
- Shows **data transformations** at each stage
- Helps in **database design** and **API planning**
- Required in most **academic project reports**

## When to Use

- During **requirements analysis**
- When designing **data pipelines**
- For **documenting system processes**
- In **academic project submissions** (very commonly expected)

---

## Level 0 — Context Diagram

```mermaid
graph LR
    USER["👤 User"]
    ADMIN["👨‍💼 Admin"]

    SYSTEM(("📄 Multilingual Document\nProcessing System"))

    USER -->|"Upload Document<br/>(Bengali/English)"| SYSTEM
    USER -->|"Select Template"| SYSTEM
    USER -->|"Request Summary"| SYSTEM
    USER -->|"Edit Content"| SYSTEM

    SYSTEM -->|"Generated Report"| USER
    SYSTEM -->|"Summary Output"| USER
    SYSTEM -->|"Exported File<br/>(PDF/DOCX/Excel)"| USER

    ADMIN -->|"Manage Templates"| SYSTEM
    ADMIN -->|"Configure Models"| SYSTEM

    SYSTEM -->|"System Logs"| ADMIN
    SYSTEM -->|"Usage Analytics"| ADMIN

    style SYSTEM fill:#FF7043,color:#fff
    style USER fill:#42A5F5,color:#fff
    style ADMIN fill:#66BB6A,color:#fff
```

---

## Level 1 — Major Process Breakdown

```mermaid
graph TB
    USER["👤 User"] 

    subgraph "1.0 Document Ingestion"
        P1["1.1 Upload<br/>Handler"]
        P2["1.2 OCR<br/>Processing"]
        P3["1.3 Language<br/>Detection"]
    end

    subgraph "2.0 Text Processing"
        P4["2.1 NLP<br/>Pipeline"]
        P5["2.2 Text<br/>Chunking"]
        P6["2.3 Embedding<br/>Generation"]
    end

    subgraph "3.0 AI Processing"
        P7["3.1 RAG<br/>Retrieval"]
        P8["3.2 LLM<br/>Generation"]
        P9["3.3 Summarization"]
    end

    subgraph "4.0 Output Generation"
        P10["4.1 Template<br/>Engine"]
        P11["4.2 Report<br/>Formatter"]
        P12["4.3 Export<br/>Engine"]
    end

    DS1[("📁 File<br/>Storage")]
    DS2[("🗄️ Vector<br/>Database")]
    DS3[("📑 Template<br/>Store")]

    USER -->|"Raw Document"| P1
    P1 -->|"Document File"| DS1
    P1 -->|"File Path"| P2
    P2 -->|"Extracted Text"| P3
    P3 -->|"Tagged Text<br/>(BN/EN)"| P4
    
    P4 -->|"Processed Text"| P5
    P5 -->|"Text Chunks"| P6
    P6 -->|"Vectors"| DS2
    
    P7 -->|"Query"| DS2
    DS2 -->|"Relevant Chunks"| P7
    P7 -->|"Context + Query"| P8
    P8 -->|"Generated Text"| P9
    
    P9 -->|"Summary"| P10
    DS3 -->|"Template Definition"| P10
    P10 -->|"Formatted Content"| P11
    P11 -->|"Final Report"| P12
    P12 -->|"PDF/DOCX/Excel"| USER

    style USER fill:#42A5F5,color:#fff
    style DS1 fill:#66BB6A,color:#000
    style DS2 fill:#66BB6A,color:#000
    style DS3 fill:#66BB6A,color:#000
```

---

## Level 2 — Document Ingestion (Process 1.0 Detailed)

```mermaid
graph TB
    INPUT["📄 Uploaded Document"]

    P1_1["1.1.1 Validate<br/>File Type"]
    P1_2["1.1.2 Extract<br/>Metadata"]
    P1_3["1.1.3 Save to<br/>Storage"]

    P2_1["1.2.1 Image<br/>Preprocessing"]
    P2_2["1.2.2 Bengali<br/>OCR"]
    P2_3["1.2.3 English<br/>OCR"]
    P2_4["1.2.4 Merge<br/>OCR Results"]

    P3_1["1.3.1 Script<br/>Detection"]
    P3_2["1.3.2 Language<br/>Tagging"]
    P3_3["1.3.3 Encoding<br/>Normalization"]

    DS["📁 File Storage"]
    OUTPUT["📝 Tagged Bilingual Text"]

    INPUT --> P1_1
    P1_1 -->|"Valid File"| P1_2
    P1_2 -->|"Metadata"| P1_3
    P1_3 --> DS

    P1_1 -->|"Image/Scan"| P2_1
    P2_1 --> P2_2
    P2_1 --> P2_3
    P2_2 -->|"Bengali Text"| P2_4
    P2_3 -->|"English Text"| P2_4

    P1_1 -->|"Digital Text"| P3_1
    P2_4 --> P3_1
    P3_1 --> P3_2
    P3_2 --> P3_3
    P3_3 --> OUTPUT

    style INPUT fill:#FF7043,color:#fff
    style OUTPUT fill:#4FC3F7,color:#000
    style DS fill:#66BB6A,color:#000
```

---

## Data Dictionary

| Data Flow | Description | Format | Source → Destination |
|-----------|-------------|--------|---------------------|
| Raw Document | User uploaded file | PDF/Image/DOCX/TXT | User → Upload Handler |
| Extracted Text | OCR output text | UTF-8 String | OCR Engine → Language Detection |
| Tagged Text | Language-annotated text | JSON {text, lang} | Language Detection → NLP Pipeline |
| Text Chunks | Segmented text pieces | Array of strings | Text Chunking → Embedding |
| Vectors | Numerical embeddings | Float Array (768d) | Embedding → Vector DB |
| Relevant Chunks | Retrieved context | Array of strings | Vector DB → RAG |
| Generated Text | LLM output | UTF-8 String | LLM → Summarization |
| Template Definition | Card layout specs | JSON Schema | Template Store → Template Engine |
| Final Report | Formatted document | HTML/JSON | Report Formatter → Export Engine |
| Export File | Downloadable file | PDF/DOCX/XLSX | Export Engine → User |

---

## DFD Symbols Reference

| Symbol | Meaning | Example |
|--------|---------|---------|
| ▭ Rectangle | External Entity | User, Admin |
| ○ Circle/Rounded | Process | OCR Processing |
| ═ Open Rectangle | Data Store | Vector Database |
| → Arrow | Data Flow | "Extracted Text" |
