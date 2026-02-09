# 5. Activity Diagram

## Mermaid Files

| File                                                             | Description                           |
| ---------------------------------------------------------------- | ------------------------------------- |
| [activity_main_workflow.mmd](activity_main_workflow.mmd)         | Complete Document Processing Workflow |
| [activity_rag_summarization.mmd](activity_rag_summarization.mmd) | RAG-Based Summarization Process       |
| [activity_template_report.mmd](activity_template_report.mmd)     | Template-Based Report Generation      |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is an Activity Diagram?

An **Activity Diagram** is a UML diagram that models the **workflow or process flow** of the system. It shows the **step-by-step activities**, **decision points**, **parallel processes**, and **flow of control** from start to finish. Think of it as a more powerful version of a flowchart with support for concurrency.

## Why Use It?

- Models **complex business logic** with branching and parallelism
- Shows **decision points** and **conditional paths**
- Illustrates **parallel activities** using fork/join bars
- Maps directly to **user workflows**
- Great for **process documentation**

## When to Use

- During **workflow design**
- When modeling **business processes**
- For showing **parallel processing** paths
- In **system behavior documentation**

---

## Activity 1: Complete Document Processing Workflow

```mermaid
graph TB
    START(("▶ Start"))
    A1["User opens web application"]
    A2["User uploads document"]

    D1{"File type?"}

    A3["Extract text directly<br/>(Digital Document)"]
    A4["Preprocess image"]

    FORK1["══ FORK ══"]
    A5["Run Bengali OCR"]
    A6["Run English OCR"]
    JOIN1["══ JOIN ══"]

    A7["Merge OCR results"]
    A8["Detect languages<br/>(Bengali/English)"]
    A9["NLP Processing<br/>(Tokenize, Clean)"]
    A10["Chunk text into segments"]
    A11["Generate embeddings<br/>(Nomic Embed)"]
    A12["Store in Vector DB"]
    A13["Document ready notification"]

    D2{"User action?"}

    A14["Generate summary<br/>via RAG + Mistral"]
    A15["Select template card"]
    A16["Ask question<br/>about document"]

    A17["Display in UI Editor"]

    D3{"User satisfied?"}

    A18["Edit content"]

    D4{"Export format?"}

    A19["Export as PDF"]
    A20["Export as DOCX"]
    A21["Export as Excel"]
    A22["Print directly"]

    A23["Download/Print"]
    ENDNODE(("⏹ End"))

    START --> A1 --> A2 --> D1

    D1 -->|"PDF/DOCX/TXT"| A3
    D1 -->|"Image/Scan"| A4

    A4 --> FORK1
    FORK1 --> A5
    FORK1 --> A6
    A5 --> JOIN1
    A6 --> JOIN1
    JOIN1 --> A7

    A3 --> A8
    A7 --> A8
    A8 --> A9 --> A10 --> A11 --> A12 --> A13 --> D2

    D2 -->|"Summarize"| A14
    D2 -->|"Use Template"| A15
    D2 -->|"Ask Question"| A16

    A14 --> A17
    A15 --> A17
    A16 --> A17

    A17 --> D3
    D3 -->|"No"| A18
    A18 --> A17
    D3 -->|"Yes"| D4

    D4 -->|"PDF"| A19
    D4 -->|"DOCX"| A20
    D4 -->|"Excel"| A21
    D4 -->|"Print"| A22

    A19 --> A23
    A20 --> A23
    A21 --> A23
    A22 --> A23

    A23 --> ENDNODE

    style START fill:#4CAF50,color:#fff
    style ENDNODE fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
    style D2 fill:#FFB74D,color:#000
    style D3 fill:#FFB74D,color:#000
    style D4 fill:#FFB74D,color:#000
    style FORK1 fill:#7E57C2,color:#fff
    style JOIN1 fill:#7E57C2,color:#fff
```

---

## Activity 2: RAG-Based Summarization Process

```mermaid
graph TB
    S(("▶ Start"))

    B1["Receive summarize request"]
    B2["Fetch document chunks<br/>from Vector DB"]
    B3["Embed summary query<br/>(Nomic Embed)"]
    B4["Perform similarity search"]
    B5["Retrieve top-K<br/>relevant chunks"]
    B6["Build RAG prompt"]
    B7["Add system instructions<br/>(bilingual support)"]
    B8["Send to Mistral LLM"]
    B9["Receive generated summary"]

    D1{"Summary quality<br/>acceptable?"}

    B10["Adjust parameters<br/>(temperature, top_k)"]
    B11["Return summary to UI"]
    B12["Display in editor"]

    E(("⏹ End"))

    S --> B1 --> B2 --> B3 --> B4 --> B5 --> B6 --> B7 --> B8 --> B9 --> D1
    D1 -->|"No"| B10 --> B8
    D1 -->|"Yes"| B11 --> B12 --> E

    style S fill:#4CAF50,color:#fff
    style E fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
```

---

## Activity 3: Template-Based Report Generation

```mermaid
graph TB
    S(("▶ Start"))

    C1["User browses<br/>template gallery"]
    C2["Select template card"]

    D1{"Template category?"}

    C3["Legal/Govt Template<br/>(Affidavit, Notice, Form)"]
    C4["Administrative Template<br/>(Minutes, Memo, Letter)"]
    C5["Analytical Template<br/>(Stats Summary, Progress)"]
    C6["Summary Card Template<br/>(Executive Brief)"]

    C7["Load template schema"]
    C8["Extract relevant data<br/>from document via LLM"]
    C9["Auto-fill template fields"]
    C10["Render formatted report"]
    C11["Display in UI editor"]

    D2{"Needs editing?"}

    C12["User edits content"]
    C13["Finalize document"]
    C14["Select export format"]
    C15["Generate & download"]

    E(("⏹ End"))

    S --> C1 --> C2 --> D1
    D1 -->|"Legal"| C3
    D1 -->|"Admin"| C4
    D1 -->|"Analytical"| C5
    D1 -->|"Summary"| C6

    C3 --> C7
    C4 --> C7
    C5 --> C7
    C6 --> C7

    C7 --> C8 --> C9 --> C10 --> C11 --> D2
    D2 -->|"Yes"| C12 --> C11
    D2 -->|"No"| C13 --> C14 --> C15 --> E

    style S fill:#4CAF50,color:#fff
    style E fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
    style D2 fill:#FFB74D,color:#000
```

---

## Activity Diagram Notation

| Symbol            | Name            | Purpose               |
| ----------------- | --------------- | --------------------- |
| ● (Filled circle) | Initial Node    | Start of workflow     |
| ◉ (Circled dot)   | Final Node      | End of workflow       |
| ▭ (Rounded rect)  | Activity/Action | A step in the process |
| ◇ (Diamond)       | Decision        | Branching point       |
| ═══ (Thick bar)   | Fork/Join       | Parallel paths        |
| → (Arrow)         | Control Flow    | Direction of process  |
