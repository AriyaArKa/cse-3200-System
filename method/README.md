# Method — Flow Diagram Reference Guide

## Multilingual Document Processing System (Bengali + English)

This folder contains **11 different diagram techniques** used to document and present the system design. Each diagram type serves a unique purpose, and together they provide **complete system documentation** suitable for academic project submissions, viva defense, and technical presentations.

---

## Project Overview

A system that processes **Bengali and English (mixed) documents** using local AI models (**Ollama — Mistral + Nomic Embed Text**) to provide:

- **Document Upload & OCR** (scanned/image support)
- **AI-Powered Summarization** (RAG-based)
- **10-15 Template Cards** (Government, Administrative, Analytical, Summary)
- **Interactive UI Editor** (edit before finalizing)
- **Multi-Format Export** (PDF, DOCX, Excel, Print)

---

## Diagram Index

| #   | Diagram Type                                     | Folder                    | Purpose                                  | Priority         |
| --- | ------------------------------------------------ | ------------------------- | ---------------------------------------- | ---------------- |
| 01  | [System Architecture](01_system_architecture/)   | `01_system_architecture/` | High-level system structure & tech stack | ⭐⭐⭐ Must Have |
| 02  | [Data Flow Diagram (DFD)](02_data_flow_diagram/) | `02_data_flow_diagram/`   | How data moves through the system        | ⭐⭐⭐ Must Have |
| 03  | [Use Case Diagram](03_use_case_diagram/)         | `03_use_case_diagram/`    | Actor-system interactions                | ⭐⭐⭐ Must Have |
| 04  | [Sequence Diagram](04_sequence_diagram/)         | `04_sequence_diagram/`    | Time-ordered message flow                | ⭐⭐⭐ Must Have |
| 05  | [Activity Diagram](05_activity_diagram/)         | `05_activity_diagram/`    | Workflow with decisions & parallelism    | ⭐⭐ Important   |
| 06  | [Component Diagram](06_component_diagram/)       | `06_component_diagram/`   | Software modules & interfaces            | ⭐⭐ Important   |
| 07  | [ER Diagram](07_er_diagram/)                     | `07_er_diagram/`          | Database structure & relationships       | ⭐⭐⭐ Must Have |
| 08  | [State Diagram](08_state_diagram/)               | `08_state_diagram/`       | Entity lifecycle states                  | ⭐⭐ Important   |
| 09  | [Flowchart](09_flowchart/)                       | `09_flowchart/`           | Step-by-step process logic               | ⭐⭐⭐ Must Have |
| 10  | [Mind Map](10_mind_map/)                         | `10_mind_map/`            | Project overview & brainstorming         | ⭐⭐ Important   |
| 11  | [Class Diagram](11_class_diagram/)               | `11_class_diagram/`       | OOP structure & relationships            | ⭐⭐ Important   |

---

## Recommended Presentation Order

### For Viva / Project Defense:

1. **Mind Map** → Give the big picture overview first
2. **System Architecture** → Show technical structure
3. **Use Case Diagram** → Show what users can do
4. **DFD (Level 0 → Level 1)** → Show data flow
5. **Flowchart** → Walk through the main process
6. **Sequence Diagram** → Show detailed interactions
7. **ER Diagram** → Show database design
8. **Demo** → Show the working system

### For Project Report:

1. System Architecture Diagram
2. Use Case Diagram
3. Data Flow Diagram (Level 0, 1, 2)
4. Activity Diagram
5. Sequence Diagram
6. ER Diagram
7. Class Diagram
8. State Diagram
9. Component Diagram
10. Flowchart

---

## How to View Diagrams

All diagrams are written in **Mermaid.js** syntax inside Markdown files. You can view them in:

| Tool                    | How to View                                          |
| ----------------------- | ---------------------------------------------------- |
| **VS Code**             | Install "Markdown Preview Mermaid Support" extension |
| **GitHub**              | Push to repo — GitHub renders Mermaid natively       |
| **Mermaid Live Editor** | Paste code at [mermaid.live](https://mermaid.live)   |
| **Notion**              | Supports Mermaid code blocks                         |
| **Obsidian**            | Native Mermaid rendering                             |

### VS Code Extension for Mermaid:

```
Name: Markdown Preview Mermaid Support
ID: bierner.markdown-mermaid
```

---

## Technology Stack Summary

| Layer          | Technology                       | Purpose                               |
| -------------- | -------------------------------- | ------------------------------------- |
| **AI/LLM**     | Ollama + Mistral                 | Local text generation & summarization |
| **Embeddings** | Nomic Embed Text                 | Document vectorization (768d)         |
| **RAG**        | LangChain                        | Retrieval Augmented Generation        |
| **Vector DB**  | ChromaDB / FAISS                 | Similarity search                     |
| **Backend**    | Python + FastAPI                 | REST API server                       |
| **Frontend**   | React / Next.js                  | Web interface                         |
| **OCR**        | Tesseract / EasyOCR              | Bengali + English text extraction     |
| **NLP**        | spaCy / NLTK                     | Bilingual text processing             |
| **Export**     | ReportLab, python-docx, openpyxl | PDF, DOCX, Excel generation           |
| **Database**   | SQLite / PostgreSQL              | User, template, report data           |

---

## All Mermaid (.mmd) Files — Quick Reference

Each diagram is available as a standalone `.mmd` file that can be opened in [Mermaid Live Editor](https://mermaid.live), VS Code, GitHub, or any Mermaid renderer.

| #   | Folder              | Mermaid File(s)                                                                                                          |
| --- | ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 01  | System Architecture | `system_architecture.mmd`                                                                                                |
| 02  | Data Flow Diagram   | `dfd_level0_context.mmd`, `dfd_level1_processes.mmd`, `dfd_level2_ingestion.mmd`                                         |
| 03  | Use Case            | `use_case.mmd`                                                                                                           |
| 04  | Sequence            | `seq_document_upload.mmd`, `seq_summarization.mmd`, `seq_template_report.mmd`, `seq_rag_query.mmd`                       |
| 05  | Activity            | `activity_main_workflow.mmd`, `activity_rag_summarization.mmd`, `activity_template_report.mmd`                           |
| 06  | Component           | `component_diagram.mmd`                                                                                                  |
| 07  | ER Diagram          | `er_diagram.mmd`                                                                                                         |
| 08  | State               | `state_document_lifecycle.mmd`, `state_report_lifecycle.mmd`, `state_user_session.mmd`                                   |
| 09  | Flowchart           | `flowchart_main_process.mmd`, `flowchart_rag_process.mmd`, `flowchart_export_process.mmd`                                |
| 10  | Mind Map            | `mindmap_project_overview.mmd`, `mindmap_tech_stack.mmd`, `mindmap_user_workflow.mmd`, `mindmap_template_categories.mmd` |
| 11  | Class               | `class_diagram.mmd`                                                                                                      |

**Total: 25 standalone Mermaid diagram files**

---

## Folder Structure

```
method/
├── README.md                              ← You are here
├── 01_system_architecture/
│   ├── README.md                          ← Explanation + embedded diagram
│   └── system_architecture.mmd            ← Standalone Mermaid file
├── 02_data_flow_diagram/
│   ├── README.md
│   ├── dfd_level0_context.mmd
│   ├── dfd_level1_processes.mmd
│   └── dfd_level2_ingestion.mmd
├── 03_use_case_diagram/
│   ├── README.md
│   └── use_case.mmd
├── 04_sequence_diagram/
│   ├── README.md
│   ├── seq_document_upload.mmd
│   ├── seq_summarization.mmd
│   ├── seq_template_report.mmd
│   └── seq_rag_query.mmd
├── 05_activity_diagram/
│   ├── README.md
│   ├── activity_main_workflow.mmd
│   ├── activity_rag_summarization.mmd
│   └── activity_template_report.mmd
├── 06_component_diagram/
│   ├── README.md
│   └── component_diagram.mmd
├── 07_er_diagram/
│   ├── README.md
│   └── er_diagram.mmd
├── 08_state_diagram/
│   ├── README.md
│   ├── state_document_lifecycle.mmd
│   ├── state_report_lifecycle.mmd
│   └── state_user_session.mmd
├── 09_flowchart/
│   ├── README.md
│   ├── flowchart_main_process.mmd
│   ├── flowchart_rag_process.mmd
│   └── flowchart_export_process.mmd
├── 10_mind_map/
│   ├── README.md
│   ├── mindmap_project_overview.mmd
│   ├── mindmap_tech_stack.mmd
│   ├── mindmap_user_workflow.mmd
│   └── mindmap_template_categories.mmd
└── 11_class_diagram/
    ├── README.md
    └── class_diagram.mmd
```
