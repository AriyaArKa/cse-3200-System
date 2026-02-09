# 9. Flowchart Diagram

## Mermaid Files

| File | Description |
|------|-------------|
| [flowchart_main_process.mmd](flowchart_main_process.mmd) | Main System Process Flow |
| [flowchart_rag_process.mmd](flowchart_rag_process.mmd) | RAG (Retrieval Augmented Generation) Process |
| [flowchart_export_process.mmd](flowchart_export_process.mmd) | Export Process Flow |

> Open `.mmd` files in [Mermaid Live Editor](https://mermaid.live), VS Code with Mermaid extension, or any Mermaid-compatible tool.

---

## What is a Flowchart?

A **Flowchart** is the most fundamental and widely understood diagram type. It shows the **step-by-step process** with clear **decision points** (Yes/No branches), **input/output** operations, and **process blocks**. Unlike activity diagrams, flowcharts are simpler and more universally recognized.

## Why Use It?

- **Simplest** and most universally understood diagram
- Shows **step-by-step logic** with decisions
- Great for **algorithm representation**
- Easy for **non-technical stakeholders** to understand
- Required in almost **every academic project**

## When to Use

- When explaining **algorithms** or **business logic**
- For **process documentation**
- In **user manuals** and **help guides**
- When presenting to **non-technical audiences**
- In **viva/defense presentations**

---

## Flowchart 1: Main System Process Flow

```mermaid
flowchart TD
    START([🟢 START])
    
    I1[/"📤 User uploads document<br/>(PDF/Image/DOCX/TXT)"/]
    
    P1["Validate file type & size"]
    D1{"Valid file?"}
    E1[/"❌ Show error message"/]
    
    D2{"Is it an image<br/>or scanned PDF?"}
    
    P2["Run OCR Engine<br/>(Bengali + English)"]
    P3["Extract text directly"]
    
    P4["Detect language<br/>(Bengali/English/Mixed)"]
    P5["NLP Processing<br/>(Tokenization, Cleaning)"]
    P6["Split into text chunks"]
    P7["Generate embeddings<br/>(Nomic Embed Text - 768d)"]
    P8["Store vectors in<br/>Vector Database"]
    
    O1[/"✅ Document processed<br/>successfully"/]
    
    D3{"What does<br/>user want?"}
    
    P9["RAG: Retrieve relevant chunks<br/>+ Generate with Mistral"]
    P10["Load template schema<br/>+ Auto-fill with LLM"]
    P11["Embed query → Search<br/>→ Generate answer"]
    
    P12["Display result in<br/>UI Editor"]
    
    D4{"User wants<br/>to edit?"}
    P13["User edits content<br/>in Rich Text Editor"]
    
    D5{"Export format?"}
    P14["Generate PDF"]
    P15["Generate DOCX"]
    P16["Generate Excel"]
    P17["Send to Printer"]
    
    O2[/"📥 Download/Print<br/>final document"/]
    
    ENDNODE([🔴 END])

    START --> I1 --> P1 --> D1
    D1 -->|"No"| E1 --> I1
    D1 -->|"Yes"| D2
    
    D2 -->|"Yes"| P2 --> P4
    D2 -->|"No"| P3 --> P4
    
    P4 --> P5 --> P6 --> P7 --> P8 --> O1 --> D3
    
    D3 -->|"Summarize"| P9
    D3 -->|"Use Template"| P10
    D3 -->|"Ask Question"| P11
    
    P9 --> P12
    P10 --> P12
    P11 --> P12
    
    P12 --> D4
    D4 -->|"Yes"| P13 --> D4
    D4 -->|"No, Finalize"| D5
    
    D5 -->|"PDF"| P14
    D5 -->|"DOCX"| P15
    D5 -->|"Excel"| P16
    D5 -->|"Print"| P17
    
    P14 --> O2
    P15 --> O2
    P16 --> O2
    P17 --> O2
    
    O2 --> ENDNODE

    style START fill:#4CAF50,color:#fff
    style ENDNODE fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
    style D2 fill:#FFB74D,color:#000
    style D3 fill:#FFB74D,color:#000
    style D4 fill:#FFB74D,color:#000
    style D5 fill:#FFB74D,color:#000
    style E1 fill:#EF5350,color:#fff
```

---

## Flowchart 2: RAG (Retrieval Augmented Generation) Process

```mermaid
flowchart TD
    START([🟢 START])
    
    I1[/"User enters query<br/>(Bengali/English/Mixed)"/]
    
    P1["Send query to<br/>Nomic Embed Text"]
    P2["Generate query<br/>vector (768 dimensions)"]
    P3["Search Vector DB<br/>for similar chunks"]
    
    D1{"Relevant chunks<br/>found?"}
    
    P4["Retrieve top-K<br/>matching chunks"]
    P5["Use general knowledge<br/>(no context)"]
    
    P6["Build prompt:<br/>System + Context + Query"]
    P7["Send to Mistral LLM<br/>via Ollama"]
    P8["Generate response"]
    
    D2{"Response in<br/>correct language?"}
    
    P9["Post-process:<br/>Language alignment"]
    
    O1[/"Display response<br/>to user"/]
    
    ENDNODE([🔴 END])

    START --> I1 --> P1 --> P2 --> P3 --> D1
    D1 -->|"Yes"| P4 --> P6
    D1 -->|"No"| P5 --> P6
    P6 --> P7 --> P8 --> D2
    D2 -->|"No"| P9 --> O1
    D2 -->|"Yes"| O1
    O1 --> ENDNODE

    style START fill:#4CAF50,color:#fff
    style ENDNODE fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
    style D2 fill:#FFB74D,color:#000
```

---

## Flowchart 3: Export Process

```mermaid
flowchart TD
    START([🟢 START])
    
    I1[/"User clicks Export"/]
    P1["Capture current editor content"]
    
    D1{"Selected format?"}
    
    subgraph "PDF Export"
        P2["Render HTML to PDF"]
        P3["Apply Bengali fonts<br/>(Kalpurush/SolaimanLipi)"]
        P4["Set page layout<br/>(A4, margins)"]
    end
    
    subgraph "DOCX Export"
        P5["Convert HTML to DOCX"]
        P6["Apply document styles"]
        P7["Embed Bengali fonts"]
    end
    
    subgraph "Excel Export"
        P8["Parse structured data"]
        P9["Map to spreadsheet cells"]
        P10["Apply formatting"]
    end
    
    P11["Generate file"]
    D2{"File generated<br/>successfully?"}
    
    E1[/"❌ Show error<br/>& retry option"/]
    O1[/"📥 Trigger download"/]
    
    ENDNODE([🔴 END])

    START --> I1 --> P1 --> D1
    D1 -->|"PDF"| P2 --> P3 --> P4 --> P11
    D1 -->|"DOCX"| P5 --> P6 --> P7 --> P11
    D1 -->|"Excel"| P8 --> P9 --> P10 --> P11
    
    P11 --> D2
    D2 -->|"No"| E1 --> P1
    D2 -->|"Yes"| O1 --> ENDNODE

    style START fill:#4CAF50,color:#fff
    style ENDNODE fill:#F44336,color:#fff
    style D1 fill:#FFB74D,color:#000
    style D2 fill:#FFB74D,color:#000
    style E1 fill:#EF5350,color:#fff
```

---

## Flowchart Symbols Reference

| Symbol | Shape | Meaning | Example |
|--------|-------|---------|---------|
| ⬭ | Rounded Rectangle / Stadium | Start/End | START, END |
| ▭ | Rectangle | Process | "Run OCR Engine" |
| ◇ | Diamond | Decision | "Valid file?" |
| ▱ | Parallelogram | Input/Output | "User uploads file" |
| → | Arrow | Flow direction | Sequential step |
