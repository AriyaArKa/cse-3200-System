# PDF OCR — Gemini 2.5 Flash

Extract structured JSON from any PDF (including Bangla text) using Google Gemini 2.5 Flash. Runs as a **Streamlit web app** or as a **CLI script**.

---

## How It Works

```
PDF
 └─► Page images (pdf.py + Poppler)
       └─► OCR via Gemini 2.5 Flash (app.py / main.py)
             └─► output_jsons/<run_id>/page_N.json   (per page)
                   └─► merged_outputs/<name>_<run_id>.json  (all pages merged)
```

---

## Requirements

- Python 3.10+
- [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) (for PDF → image conversion)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/AriyaArKa/cse-3200-System.git
cd cse-3200-System/systemProject/OCR
```

### 2. Create & activate a virtual environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install google-genai streamlit Pillow python-dotenv pdf2image
```

### 4. Install Poppler (Windows only)

1. Download the latest release from [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases)
2. Extract it (e.g. to `D:\tools\poppler\`)
3. Open `pdf.py` and update `POPPLER_PATH`:

```python
POPPLER_PATH = r"D:\tools\poppler\Library\bin"  # ← change this
```

On macOS/Linux, Poppler is detected automatically (`brew install poppler` / `apt install poppler-utils`).

### 5. Configure your API key

```bash
# Copy the example file
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux

# Then edit .env and paste your key:
GEMINI_API_KEY=your_gemini_api_key_here
```

> ⚠️ **Never commit `.env` to git.** It is already in `.gitignore`.

---

## Run — Streamlit Web App (recommended)

```bash
# Make sure the venv is activated first
python -m streamlit run app.py
```

Open **http://localhost:8501** in your browser, upload a PDF, and click **Run OCR Pipeline**.

---

## Run — CLI Script

Edit `main.py` and set the PDF filename:

```python
PDF_FILE = "your_file.pdf"
```

Then run:

```bash
python main.py
```

Outputs are saved to:

- `output_jsons/` — one JSON per page
- `merged_outputs/` — single merged JSON for the whole PDF

---

## Project Structure

```
OCR/
├── app.py            # Streamlit web app
├── main.py           # CLI pipeline
├── pdf.py            # PDF → image converter
├── .env              # Your API key (git-ignored)
├── .env.example      # Template — safe to commit
├── .gitignore
├── output_images/    # Generated page images (git-ignored)
├── output_jsons/     # Per-page OCR JSON files (git-ignored)
└── merged_outputs/   # Final merged JSON per run (git-ignored)
```

---

## Troubleshooting

| Problem                                                 | Fix                                                                                                                  |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ImportError: cannot import name 'genai' from 'google'` | Make sure you activated the venv before running: `.\venv\Scripts\Activate.ps1` then `python -m streamlit run app.py` |
| `GEMINI_API_KEY not found`                              | Create `.env` from `.env.example` and add your key                                                                   |
| `PDF not found`                                         | Place your PDF in the `OCR/` folder and update `PDF_FILE` in `main.py`                                               |
| Broken Poppler path                                     | Update `POPPLER_PATH` in `pdf.py` to match your Poppler install location                                             |
| Bangla text garbled                                     | Ensure your terminal / editor uses **UTF-8** encoding                                                                |
