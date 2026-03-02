# Gemini OCR — Document Processing System

Production-ready backend that converts multi-page PDFs into structured JSON using Google Gemini Vision API.

---

## Features

| Capability            | Details                                                                              |
| --------------------- | ------------------------------------------------------------------------------------ |
| **PDF → Images**      | 300 DPI via `pdf2image` / Poppler                                                    |
| **AI OCR**            | Google Gemini Vision (`gemini-2.0-flash`)                                            |
| **Structured Output** | Tables, key-value pairs, line items                                                  |
| **Auto-detection**    | Invoice, form, government notice, table, etc.                                        |
| **Validation**        | Invoice total checks, low-confidence flags, OCR digit correction, date normalisation |
| **Retry Logic**       | Up to 3 retries with JSON correction prompt                                          |
| **Async**             | Concurrent per-page OCR with semaphore rate-limiting                                 |

---

## Project Structure

```
geminiOCR/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + /upload-pdf endpoint
│   ├── pdf_processor.py     # PDF → image conversion
│   ├── ocr_service.py       # Gemini Vision API integration
│   ├── document_parser.py   # Post-processing & validation
│   ├── schemas.py           # Pydantic models
│   └── utils.py             # Config, logging, helpers
├── requirements.txt
├── .env                      # Your API key (git-ignored)
├── .env.example
└── README.md
```

---

## Prerequisites

1. **Python 3.11+**
2. **Poppler** (required by `pdf2image`)

### Install Poppler

**Windows** — download from https://github.com/osber/poppler-windows/releases and add the `bin/` folder to your system `PATH`.

**macOS** — `brew install poppler`

**Ubuntu/Debian** — `sudo apt-get install poppler-utils`

3. **Google Gemini API key** — get one at https://aistudio.google.com/app/apikey

---

## Quick Start

```bash
# 1. Clone & enter project
cd geminiOCR

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 5. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API docs are at **http://localhost:8000/docs** (Swagger UI).

---

## API Usage

### `POST /upload-pdf`

Upload a PDF file and receive structured OCR results.

#### cURL Example

```bash
curl -X POST http://localhost:8000/upload-pdf \
  -F "file=@/path/to/document.pdf" \
  | python -m json.tool
```

#### PowerShell Example

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/upload-pdf" `
  -Method Post `
  -InFile ".\document.pdf" `
  -ContentType "multipart/form-data"
$response | ConvertTo-Json -Depth 10
```

#### Python Example

```python
import requests

with open("document.pdf", "rb") as f:
    resp = requests.post(
        "http://localhost:8000/upload-pdf",
        files={"file": ("document.pdf", f, "application/pdf")},
    )
print(resp.json())
```

### Response Format

```json
{
  "success": true,
  "data": {
    "document_type": "invoice",
    "total_pages": 2,
    "pages": [
      {
        "page_number": 1,
        "raw_text": "Invoice #12345 ...",
        "tables": [
          {
            "headers": ["Item", "Qty", "Price", "Total"],
            "rows": [["Widget A", "2", "10.00", "20.00"]]
          }
        ],
        "key_value_pairs": {
          "invoice_number": "12345",
          "date": "2025-03-01",
          "total": "20.00"
        },
        "line_items": [
          {
            "description": "Widget A",
            "quantity": "2",
            "unit_price": "10.00",
            "total": "20.00"
          }
        ],
        "confidence_score": 0.95
      }
    ]
  },
  "validation_flags": [],
  "error": null
}
```

### `GET /health`

Returns `{"status": "ok"}`.

---

## Environment Variables

| Variable           | Required | Default | Description                  |
| ------------------ | -------- | ------- | ---------------------------- |
| `GEMINI_API_KEY`   | ✅       | —       | Google Gemini API key        |
| `MAX_FILE_SIZE_MB` | —        | `50`    | Max upload size in MB        |
| `PDF_DPI`          | —        | `300`   | DPI for PDF→image conversion |
| `MAX_RETRIES`      | —        | `3`     | Gemini API retry count       |

---

## Validation & Post-Processing

- **Invoice total validation** — sums line item totals and compares against the document total field
- **Low-confidence flagging** — pages with confidence < 0.85 are flagged
- **OCR digit correction** — common substitutions like `O→0`, `l→1` in numeric fields
- **Date normalisation** — date values are normalised to ISO 8601 (`YYYY-MM-DD`)
- **Multi-page merge** — line items across pages are aggregated with a computed total

---

## Scaling for Production

### Docker Deployment

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t gemini-ocr .
docker run -p 8000:8000 --env-file .env gemini-ocr
```

### Task Queuing (Celery + Redis)

For large documents (50+ pages), offload processing to a Celery worker:

1. Add `celery[redis]` to `requirements.txt`
2. Create a Celery task that wraps the OCR pipeline
3. The `/upload-pdf` endpoint returns a `job_id` immediately
4. Add a `GET /status/{job_id}` endpoint for polling
5. Store results in Redis or a database

### Cloud Deployment

| Platform   | Approach                                                                               |
| ---------- | -------------------------------------------------------------------------------------- |
| **GCP**    | Cloud Run (auto-scaling containers) + Cloud Storage for PDFs + Pub/Sub for async       |
| **AWS**    | ECS Fargate or Lambda + S3 + SQS                                                       |
| **Hybrid** | Use Google Cloud Vision API as a first-pass OCR, then Gemini for structured extraction |

### Combining with Google Cloud Vision API

For maximum OCR accuracy on scanned/handwritten documents:

1. Use Cloud Vision API for raw text extraction (higher accuracy on degraded scans)
2. Feed the extracted text + original image into Gemini for structured parsing
3. This two-pass approach improves accuracy by ~15-20% on poor-quality scans

---

## License

MIT
