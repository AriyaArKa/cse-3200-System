# 8. State Diagram

## Mermaid Files

| File                                                         | Description               |
| ------------------------------------------------------------ | ------------------------- |
| [state_document_lifecycle.mmd](state_document_lifecycle.mmd) | Document Lifecycle States |
| [state_report_lifecycle.mmd](state_report_lifecycle.mmd)     | Report Lifecycle States   |
| [state_user_session.mmd](state_user_session.mmd)             | User Session States       |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a State Diagram?

A **State Diagram** (also called State Machine Diagram) shows the **different states** an object or entity can be in throughout its lifecycle, and the **transitions (events)** that cause it to move from one state to another. It answers: _"What stages does this entity go through?"_

## Why Use It?

- Models **lifecycle of key entities** (Document, Report, etc.)
- Shows **valid state transitions** and their triggers
- Helps in **error handling** and **edge case identification**
- Ensures all **states are accounted for** in the implementation
- Useful for **status tracking** in UI/UX design

## When to Use

- When entities have **multiple states** (e.g., document: uploaded → processing → ready)
- For **workflow management** features
- When designing **status indicators** in UI
- During **business logic validation**

---

## State Diagram 1: Document Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Uploaded : User uploads file

    Uploaded --> Validating : System validates file

    Validating --> Invalid : Validation fails
    Validating --> Processing : Validation passes

    Invalid --> [*] : User notified, file discarded

    Processing --> OCR_Running : Image/Scanned document
    Processing --> Text_Extracting : Digital document

    OCR_Running --> Text_Extracting : OCR complete

    Text_Extracting --> Language_Detecting : Text extracted

    Language_Detecting --> NLP_Processing : Languages tagged

    NLP_Processing --> Chunking : Text processed

    Chunking --> Embedding : Chunks created

    Embedding --> Ready : Vectors stored

    Ready --> Summarizing : User requests summary
    Ready --> Querying : User asks question
    Ready --> Reporting : User selects template

    Summarizing --> Ready : Summary generated
    Querying --> Ready : Answer returned
    Reporting --> Ready : Report created

    Ready --> Archived : User archives document

    Processing --> Error : Processing fails
    OCR_Running --> Error : OCR fails
    Embedding --> Error : Embedding fails

    Error --> Processing : Retry
    Error --> [*] : Abandoned

    Archived --> Ready : User restores
    Archived --> [*] : User deletes
```

---

## State Diagram 2: Report Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Template_Selected : User picks template

    Template_Selected --> Data_Loading : Load document data

    Data_Loading --> Generating : LLM filling template

    Generating --> Draft : Report generated

    Draft --> Editing : User opens editor

    Editing --> Draft : Auto-save
    Editing --> Preview : User clicks preview

    Preview --> Editing : User continues editing
    Preview --> Finalized : User approves

    Finalized --> Exporting : User selects format

    Exporting --> Exported_PDF : PDF selected
    Exporting --> Exported_DOCX : DOCX selected
    Exporting --> Exported_Excel : Excel selected
    Exporting --> Printing : Print selected

    Exported_PDF --> Downloaded : File ready
    Exported_DOCX --> Downloaded : File ready
    Exported_Excel --> Downloaded : File ready
    Printing --> Printed : Print job sent

    Downloaded --> [*]
    Printed --> [*]

    Generating --> Error : Generation fails
    Exporting --> Error : Export fails
    Error --> Draft : Retry
    Error --> [*] : Abandon
```

---

## State Diagram 3: User Session States

```mermaid
stateDiagram-v2
    [*] --> Unauthenticated : Open application

    Unauthenticated --> Authenticating : Submit credentials

    Authenticating --> Authenticated : Login success
    Authenticating --> Unauthenticated : Login failed

    Authenticated --> Dashboard : Load dashboard

    Dashboard --> Uploading : Upload document
    Dashboard --> BrowsingTemplates : View templates
    Dashboard --> ViewingDocuments : View documents

    Uploading --> Dashboard : Upload complete
    BrowsingTemplates --> Dashboard : Back
    ViewingDocuments --> Dashboard : Back

    ViewingDocuments --> Summarizing : Request summary
    ViewingDocuments --> Querying : Ask question

    Summarizing --> ViewingDocuments : Done
    Querying --> ViewingDocuments : Done

    BrowsingTemplates --> ReportGeneration : Select template
    ReportGeneration --> EditingReport : Report ready
    EditingReport --> ExportingReport : Export
    ExportingReport --> Dashboard : Complete

    Authenticated --> Unauthenticated : Logout
    Authenticated --> SessionExpired : Timeout
    SessionExpired --> Unauthenticated : Redirect to login
```

---

## State Transition Table: Document

| Current State      | Event/Trigger     | Next State         | Action                    |
| ------------------ | ----------------- | ------------------ | ------------------------- |
| —                  | Upload file       | Uploaded           | Save file to storage      |
| Uploaded           | Validate          | Validating         | Check file type, size     |
| Validating         | Valid             | Processing         | Begin processing pipeline |
| Validating         | Invalid           | Invalid            | Show error message        |
| Processing         | Image detected    | OCR_Running        | Start OCR engine          |
| Processing         | Text file         | Text_Extracting    | Direct text extraction    |
| OCR_Running        | OCR complete      | Text_Extracting    | Merge OCR results         |
| Text_Extracting    | Done              | Language_Detecting | Detect Bengali/English    |
| Language_Detecting | Tagged            | NLP_Processing     | Apply NLP pipeline        |
| NLP_Processing     | Processed         | Chunking           | Split into segments       |
| Chunking           | Chunked           | Embedding          | Generate vectors          |
| Embedding          | Stored            | Ready              | Document available        |
| Ready              | Summarize request | Summarizing        | Run RAG + Mistral         |
| Ready              | Template select   | Reporting          | Generate report           |
| Ready              | Archive           | Archived           | Move to archive           |
| Error              | Retry             | Processing         | Restart pipeline          |

---

## State Color Legend

| Color       | Meaning                 |
| ----------- | ----------------------- |
| Default     | Normal processing state |
| Start (●)   | Initial state           |
| End (◉)     | Terminal state          |
| Error paths | Failure recovery flows  |
