# 6. Component Diagram

## Mermaid Files

| File | Description |
|------|-------------|
| [component_diagram.mmd](component_diagram.mmd) | Full System Component Diagram with interfaces |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a Component Diagram?

A **Component Diagram** is a UML structural diagram that shows the **software components**, their **interfaces**, and the **dependencies** between them. It focuses on the **physical organization** of code — packages, libraries, modules, and how they connect through well-defined interfaces.

## Why Use It?

- Shows **modular structure** of the software
- Defines **interfaces** between components
- Illustrates **dependencies** and **coupling**
- Helps in **system decomposition** and **team assignment**
- Essential for **software architecture documentation**

## When to Use

- During **system design** and **modular planning**
- When planning **microservices** or **modules**
- For **dependency analysis**
- When assigning work to **development teams**

---

## Full System Component Diagram

```mermaid
graph TB
    subgraph "Frontend Components"
        FC1["📦 DocumentUploader<br/>Component"]
        FC2["📦 TemplateGallery<br/>Component"]
        FC3["📦 RichTextEditor<br/>Component"]
        FC4["📦 ExportManager<br/>Component"]
        FC5["📦 DashboardUI<br/>Component"]
    end

    subgraph "API Layer Components"
        AC1["📦 AuthController"]
        AC2["📦 DocumentController"]
        AC3["📦 SummaryController"]
        AC4["📦 TemplateController"]
        AC5["📦 ExportController"]
        AC6["📦 QueryController"]
    end

    subgraph "Core Processing Components"
        CC1["📦 OCRService<br/>──────────<br/>◯ ITextExtractor"]
        CC2["📦 NLPService<br/>──────────<br/>◯ ILanguageProcessor"]
        CC3["📦 ChunkingService<br/>──────────<br/>◯ ITextChunker"]
        CC4["📦 EmbeddingService<br/>──────────<br/>◯ IEmbedder"]
    end

    subgraph "AI Components"
        AI1["📦 RAGEngine<br/>──────────<br/>◯ IRetriever<br/>◯ IGenerator"]
        AI2["📦 OllamaClient<br/>──────────<br/>◯ ILLMProvider"]
        AI3["📦 SummarizationEngine<br/>──────────<br/>◯ ISummarizer"]
    end

    subgraph "Output Components"
        OC1["📦 TemplateEngine<br/>──────────<br/>◯ ITemplateRenderer"]
        OC2["📦 PDFExporter<br/>──────────<br/>◯ IExporter"]
        OC3["📦 DOCXExporter<br/>──────────<br/>◯ IExporter"]
        OC4["📦 ExcelExporter<br/>──────────<br/>◯ IExporter"]
    end

    subgraph "Data Access Components"
        DC1["📦 VectorDBClient<br/>──────────<br/>◯ IVectorStore"]
        DC2["📦 FileStorageClient<br/>──────────<br/>◯ IFileStore"]
        DC3["📦 TemplateRepository<br/>──────────<br/>◯ IRepository"]
    end

    FC1 -->|"HTTP"| AC2
    FC2 -->|"HTTP"| AC4
    FC3 -->|"HTTP"| AC3
    FC4 -->|"HTTP"| AC5
    FC5 -->|"HTTP"| AC6

    AC2 --> CC1
    AC2 --> CC2
    AC3 --> AI3
    AC4 --> OC1
    AC5 --> OC2
    AC5 --> OC3
    AC5 --> OC4
    AC6 --> AI1

    CC1 --> CC2
    CC2 --> CC3
    CC3 --> CC4
    CC4 --> DC1

    AI1 --> AI2
    AI1 --> DC1
    AI3 --> AI2
    AI1 --> CC4

    OC1 --> DC3

    style FC1 fill:#42A5F5,color:#fff
    style FC2 fill:#42A5F5,color:#fff
    style FC3 fill:#42A5F5,color:#fff
    style FC4 fill:#42A5F5,color:#fff
    style FC5 fill:#42A5F5,color:#fff
    style AI1 fill:#E91E63,color:#fff
    style AI2 fill:#E91E63,color:#fff
    style AI3 fill:#E91E63,color:#fff
    style DC1 fill:#66BB6A,color:#000
    style DC2 fill:#66BB6A,color:#000
    style DC3 fill:#66BB6A,color:#000
```

---

## Interface Definitions

| Interface | Component | Methods |
|-----------|-----------|---------|
| `ITextExtractor` | OCRService | `extract_text(file) → str` |
| `ILanguageProcessor` | NLPService | `detect_language(text) → lang`, `process(text) → tokens` |
| `ITextChunker` | ChunkingService | `chunk(text, size) → chunks[]` |
| `IEmbedder` | EmbeddingService | `embed(text) → vector[768]` |
| `IRetriever` | RAGEngine | `retrieve(query, top_k) → chunks[]` |
| `IGenerator` | RAGEngine | `generate(prompt, context) → str` |
| `ILLMProvider` | OllamaClient | `generate(model, prompt) → str` |
| `ISummarizer` | SummarizationEngine | `summarize(document) → str` |
| `ITemplateRenderer` | TemplateEngine | `render(template_id, data) → html` |
| `IExporter` | PDF/DOCX/ExcelExporter | `export(content, format) → file` |
| `IVectorStore` | VectorDBClient | `store(vector, metadata)`, `search(vector) → results[]` |
| `IFileStore` | FileStorageClient | `save(file) → path`, `load(path) → file` |
| `IRepository` | TemplateRepository | `get(id) → template`, `list() → templates[]` |

---

## Component Dependencies Matrix

| Component | Depends On |
|-----------|-----------|
| DocumentUploader | AuthController, DocumentController |
| OCRService | Tesseract/EasyOCR (external lib) |
| NLPService | spaCy, NLTK (external libs) |
| EmbeddingService | OllamaClient (Nomic Embed) |
| RAGEngine | EmbeddingService, VectorDBClient, OllamaClient |
| SummarizationEngine | OllamaClient (Mistral) |
| TemplateEngine | TemplateRepository, Jinja2 |
| PDFExporter | ReportLab/WeasyPrint (external lib) |
| DOCXExporter | python-docx (external lib) |
| ExcelExporter | openpyxl (external lib) |

---

## Package Structure

```
rag_project/
├── frontend/                  # Frontend Components
│   ├── components/
│   │   ├── DocumentUploader/
│   │   ├── TemplateGallery/
│   │   ├── RichTextEditor/
│   │   └── ExportManager/
│   └── pages/
├── backend/                   # API + Core Components
│   ├── api/
│   │   ├── auth_controller.py
│   │   ├── document_controller.py
│   │   ├── summary_controller.py
│   │   ├── template_controller.py
│   │   └── export_controller.py
│   ├── services/
│   │   ├── ocr_service.py
│   │   ├── nlp_service.py
│   │   ├── chunking_service.py
│   │   ├── embedding_service.py
│   │   ├── rag_engine.py
│   │   ├── summarization_engine.py
│   │   └── template_engine.py
│   ├── exporters/
│   │   ├── pdf_exporter.py
│   │   ├── docx_exporter.py
│   │   └── excel_exporter.py
│   └── data/
│       ├── vector_db_client.py
│       ├── file_storage_client.py
│       └── template_repository.py
└── templates/                 # Template Definitions
    └── cards/
```
