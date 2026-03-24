# 11. Class Diagram (Bonus)

## Mermaid Files

| File                                   | Description                                           |
| -------------------------------------- | ----------------------------------------------------- |
| [class_diagram.mmd](class_diagram.mmd) | Core Classes with attributes, methods & relationships |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a Class Diagram?

A **Class Diagram** is a UML structural diagram that shows the **classes** in the system, their **attributes**, **methods**, and the **relationships** between them (inheritance, composition, association). It is the blueprint for **object-oriented design**.

## Why Use It?

- Defines **object-oriented structure** of the codebase
- Shows **inheritance and composition** relationships
- Identifies **methods and attributes** per class
- Foundation for **code implementation**
- Commonly required in **software engineering courses**

## When to Use

- During **detailed design phase**
- When planning **class hierarchy** and **code structure**
- For **API and service layer design**
- In **project documentation** for developers

---

## Core Classes Diagram

```mermaid
classDiagram
    class User {
        -int user_id
        -string username
        -string email
        -string password_hash
        -string role
        +login(credentials) bool
        +logout() void
        +uploadDocument(file) Document
        +getDocuments() Document[]
    }

    class Document {
        -int document_id
        -string file_name
        -string file_path
        -string file_type
        -string status
        -string extracted_text
        +validate() bool
        +extractText() string
        +getChunks() DocumentChunk[]
        +getSummary() Summary
    }

    class DocumentChunk {
        -int chunk_id
        -int chunk_index
        -string chunk_text
        -string language_tag
        -float[] vector
        +generateEmbedding() float[]
        +getLanguage() string
    }

    class OCRService {
        -string engine_type
        +extractFromImage(image) string
        +extractBengali(image) string
        +extractEnglish(image) string
        +mergeResults(bn_text, en_text) string
    }

    class NLPService {
        +detectLanguage(text) string
        +tokenize(text) string[]
        +cleanText(text) string
        +chunkText(text, size) DocumentChunk[]
    }

    class EmbeddingService {
        -string model_name
        -int dimensions
        +embed(text) float[]
        +embedBatch(texts) float[][]
    }

    class RAGEngine {
        -VectorDBClient vectorDB
        -EmbeddingService embedder
        -LLMClient llm
        +retrieve(query, top_k) DocumentChunk[]
        +generate(query, context) string
        +queryDocument(doc_id, question) string
    }

    class LLMClient {
        -string model_name
        -string base_url
        -float temperature
        +generate(prompt) string
        +summarize(text) string
        +fillTemplate(template, data) string
    }

    class Template {
        -int template_id
        -string name
        -string category
        -json schema
        -string html_layout
        +render(data) string
        +validate(data) bool
        +getFields() string[]
    }

    class Report {
        -int report_id
        -string title
        -string content_html
        -string status
        +edit(new_content) void
        +preview() string
        +export(format) File
    }

    class ExportService {
        +exportPDF(content) File
        +exportDOCX(content) File
        +exportExcel(content) File
        +print(content) void
    }

    class VectorDBClient {
        -string db_path
        +store(vector, metadata) void
        +search(query_vector, top_k) Result[]
        +delete(doc_id) void
    }

    class Summary {
        -int summary_id
        -string summary_text
        -string model_used
        -float processing_time
        +regenerate() string
        +edit(new_text) void
    }

    User "1" --> "*" Document : uploads
    User "1" --> "*" Report : creates

    Document "1" --> "*" DocumentChunk : contains
    Document "1" --> "*" Summary : has

    Template "1" --> "*" Report : generates

    RAGEngine --> VectorDBClient : uses
    RAGEngine --> EmbeddingService : uses
    RAGEngine --> LLMClient : uses

    Document --> OCRService : processed by
    Document --> NLPService : processed by
    DocumentChunk --> EmbeddingService : embedded by

    Report --> ExportService : exported by
    Report --> Template : based on

    LLMClient --> Summary : generates
```

---

## Relationship Types

| Relationship     | Symbol | Example                              |
| ---------------- | ------ | ------------------------------------ |
| **Association**  | →      | User → Document (uploads)            |
| **Composition**  | ◆→     | Document ◆→ DocumentChunk (contains) |
| **Dependency**   | ..>    | RAGEngine ..> LLMClient (uses)       |
| **Inheritance**  | ▷      | PDFExporter ▷ ExportService          |
| **Multiplicity** | 1..\*  | One User has many Documents          |

---

## Design Patterns Used

| Pattern        | Where Applied                  | Purpose                                   |
| -------------- | ------------------------------ | ----------------------------------------- |
| **Strategy**   | ExportService (PDF/DOCX/Excel) | Swap export formats dynamically           |
| **Factory**    | TemplateEngine                 | Create different template types           |
| **Facade**     | RAGEngine                      | Simplified interface to complex subsystem |
| **Repository** | VectorDBClient                 | Abstract data access layer                |
| **Observer**   | Document status changes        | Notify UI of processing updates           |
| **Singleton**  | LLMClient (Ollama connection)  | Single connection instance                |
