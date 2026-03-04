# PerfectOCR v2.0 — Hybrid OCR System

**Intelligent OCR with cost optimization: Fast local OCR (Tesseract) + AI models (Gemini/GPT-4o) only when needed**

---

## 🚀 What's New in v2.0

### 1. **Hybrid OCR Strategy** ⚡

- **Fast Track**: Simple English documents → Tesseract OCR (instant, no API calls)
- **AI Track**: Complex/Bangla/handwriting → Gemini 2.5 Flash + GPT-4o fallback
- **Intelligent Routing**: Automatically detects when AI is needed

### 2. **Bengali Numeral Accuracy** 🔢

- Enhanced prompt with visual characteristics for each digit (০-৯)
- Specific confusion pair detection (৩ vs ৫, ৮ vs ৪, ৬ vs ৯, ২ vs ৩)
- Digit-by-digit verification protocol
- Date validation (day ≤ 31, month ≤ 12)

### 3. **Image Descriptions** 🖼️

- No more `[IMAGE]` placeholders
- Detailed descriptions of logos, seals, emblems, photographs
- Example: "University emblem of KUET showing the official seal with Bengali text"

### 4. **Handwriting Extraction** ✍️

- Character-by-character extraction rules
- Signature detection (describe rather than guess)
- Contextual Bangla word completion

### 5. **Cost Optimization** 💰

- **Before v2.0**: 2 API calls per page (dual strategy)
- **v2.0**: 0-1 API calls per page (Tesseract → Gemini only if needed)
- For English-only PDFs: **0 API calls** (100% Tesseract)

---

## 🎯 How It Works

### Decision Flow

```
PDF Page → Convert to Image (250 DPI)
    ↓
[Fast OCR: Tesseract]
    ↓
Confidence >= 75% & English text?
    ├─ YES → Use Tesseract result ✅ (0 API calls)
    └─ NO → Route to AI OCR
         ↓
    [Gemini 2.5 Flash]
         ↓
    Gemini fails?
         └─ YES → [GPT-4o Fallback]
```

### When AI OCR is Used

AI models (Gemini/GPT-4o) are called only when:

1. **Low Tesseract confidence** (< 75%)
2. **Non-Latin scripts detected** (Bangla, Arabic, etc.)
3. **Too little text extracted** (< 50 chars) → likely handwriting/complex layout
4. **Many low-confidence blocks** (> 30% of blocks)

---

## 📦 Installation

### Basic Setup (AI OCR only)

```bash
pip install -r requirements.txt
```

### Fast OCR Setup (Recommended)

1. **Install Python package**:

   ```bash
   pip install pytesseract
   ```

2. **Install Tesseract binary**:
   - **Windows**: Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) (e.g., `tesseract-install.exe`)
   - **Linux**: `sudo apt install tesseract-ocr`
   - **Mac**: `brew install tesseract`

3. **Verify installation**:
   ```bash
   python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
   ```

---

## 🎮 Usage

### Streamlit Dashboard

```bash
streamlit run PerfectOCR/app.py
```

Features:

- Upload PDF
- Auto-strategy (Gemini Primary + Fast OCR optimization)
- Real-time progress tracking
- Download JSON/TXT results
- View extraction notes, confidence scores, block sources

### CLI

```bash
python -m PerfectOCR.main input.pdf --output ./output
```

---

## 📊 Performance Metrics

### English-Only PDF (10 pages)

- **v1.0 (Dual)**: 20 API calls (10 Gemini + 10 GPT-4o)
- **v2.0 (Fast OCR)**: 0 API calls ✅

### Mixed Bangla/English PDF (10 pages)

- **v1.0 (Dual)**: 20 API calls
- **v2.0 (Hybrid)**: 5-10 API calls (depends on complexity)

### Handwriting/Complex PDF (10 pages)

- **v1.0 (Dual)**: 20 API calls
- **v2.0 (Hybrid)**: 10-15 API calls (Gemini primary, GPT-4o fallback)

---

## 🔧 Configuration

### Default Settings (`config.py`)

```python
DEFAULT_STRATEGY = "gemini_primary"  # Auto-selects Tesseract → Gemini → GPT-4o
DPI = 250  # Higher DPI for better digit/handwriting recognition
CORRECTION_MODEL = "gemini-2.5-flash"  # Bangla correction (fewer GPT-4o calls)
```

### Tesseract Settings (`fast_ocr.py`)

```python
# AI is used when Tesseract confidence < 75%
# Or when non-Latin characters detected
# Or when < 50 chars extracted
```

---

## 📝 Output Format

### JSON Structure

```json
{
  "document": {
    "source": "file.pdf",
    "total_pages": 10,
    "models_used": ["gemini-2.5-flash", "gpt-4o"],
    "has_handwriting": true
  },
  "pages": [
    {
      "page_number": 1,
      "content_blocks": [
        {
          "block_id": 1,
          "type": "image",
          "text": "University emblem of KUET...",
          "confidence": "high",
          "_source": "gemini" // or "tesseract" or "gpt4o"
        }
      ],
      "processing_time_ms": 1234
    }
  ]
}
```

### Metrics Tracking

```json
{
  "gemini_calls": 5,
  "gpt4o_calls": 0,
  "correction_calls": 5,
  "tesseract_only_pages": 5, // Pages processed without AI
  "total_api_calls": 10
}
```

---

## 🐛 Troubleshooting

### Streamlit Duplicate Key Error

**Fixed in v2.0**: Uses `id(result)` + page index for unique keys.

### Tesseract Not Found

```
RuntimeError: Tesseract not found
```

**Solution**: Install Tesseract binary (see Installation section)

### Bengali Digit Errors

**v2.0 Fix**: Enhanced prompt with:

- Visual characteristics for each digit
- 6-step verification protocol
- Context-free digit extraction (no auto-correction)

---

## 🎓 OCR Engineer's Perspective

### Why Hybrid Strategy?

1. **Cost-Benefit Analysis**:
   - Tesseract: Free, instant, 95%+ accuracy for English
   - Gemini: $0.01/1K tokens, excellent for Bangla
   - GPT-4o: $0.03/1K tokens, best for complex layouts

2. **Accuracy Hierarchy**:
   - **English printed text**: Tesseract ≈ Gemini ≈ GPT-4o (use fastest)
   - **Bengali text**: Gemini > GPT-4o >> Tesseract
   - **Handwriting**: GPT-4o > Gemini >> Tesseract
   - **Tables/Forms**: GPT-4o ≥ Gemini >> Tesseract

3. **Optimization Pattern**:
   ```
   Fast & Good Enough (Tesseract)
   → Specialized & Reliable (Gemini for Bangla)
   → Expensive & Accurate (GPT-4o for edge cases)
   ```

---

## 📚 API Reference

### FastOCREngine

```python
from PerfectOCR.fast_ocr import FastOCREngine, should_use_ai_ocr

engine = FastOCREngine()
result = engine.extract_page(image_b64, page_num=1)

# Check if AI is needed
needs_ai = should_use_ai_ocr(result)
```

### PerfectOCRPipeline

```python
from PerfectOCR.pipeline import PerfectOCRPipeline

pipeline = PerfectOCRPipeline(
    pdf_path="document.pdf",
    strategy="gemini_primary",  # Auto-uses Tesseract when possible
    enable_correction=True,
    dpi=250
)

result = pipeline.run()
print(f"Tesseract pages: {pipeline.tracker.tesseract_only_pages}")
```

---

## 🔮 Future Enhancements

- [ ] Multi-language Tesseract support (Bengali, Arabic, etc.)
- [ ] GPU-accelerated image preprocessing
- [ ] Caching layer for repeated pages
- [ ] Real-time streaming OCR
- [ ] Custom confidence threshold configuration

---

## 📄 License

MIT License

---

## 🤝 Contributing

Issues and PRs welcome! Focus areas:

- Bengali digit accuracy improvements
- Handwriting extraction optimization
- New language support

---

**PerfectOCR v2.0** — Smart, Fast, Accurate 🚀
