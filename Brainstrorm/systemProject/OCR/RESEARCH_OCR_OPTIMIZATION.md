# Research Summary: Efficient Large PDF OCR Processing

## Executive Summary

This research document summarizes best practices for efficient large PDF OCR processing, with specific focus on Gemini API optimizations, parallel processing strategies, and techniques to achieve sub-10-second per-page processing times.

---

## 1. Key Optimization Techniques

### 1.1 Native PDF Processing (Most Impactful)

The **single most important optimization** is to use Gemini's native PDF processing instead of converting to images:

```python
from google import genai
from google.genai import types

client = genai.Client()

# Upload PDF directly - NO image conversion needed
sample_doc = client.files.upload(
    file='document.pdf',
    config=dict(mime_type='application/pdf')
)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[sample_doc, "Extract all text from this document"]
)
```

**Benefits:**

- Supports up to **1000 pages** per PDF
- Up to **50MB** file size
- Each page = only **258 tokens** (vs 1120+ for images)
- Native text extraction included (not charged for embedded text tokens)
- No PDF→image conversion time

### 1.2 Media Resolution Control

Use the `media_resolution` parameter to control token usage:

| Resolution | Image Tokens | PDF Tokens         | Best For                             |
| ---------- | ------------ | ------------------ | ------------------------------------ |
| LOW        | 280          | 280 + Native Text  | Simple text extraction               |
| MEDIUM     | 560          | 560 + Native Text  | **Standard documents (recommended)** |
| HIGH       | 1120         | 1120 + Native Text | Complex layouts, tables              |
| ULTRA_HIGH | 2240         | N/A                | Computer use only                    |

**Recommendation for OCR:** Use `MEDIA_RESOLUTION_MEDIUM` - quality saturates at medium for standard documents.

```python
from google.genai import types

config = types.GenerateContentConfig(
    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
)

response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents=[pdf_file, prompt],
    config=config
)
```

### 1.3 Batch API for Large Volumes (50% Cost Reduction)

For non-urgent processing, use the Batch API at **50% cost**:

```python
from google import genai
import json

client = genai.Client()

# Create JSONL file with all page requests
requests = []
for i, page_img in enumerate(pages):
    requests.append({
        "key": f"page-{i+1}",
        "request": {
            "contents": [
                {"parts": [{"text": OCR_PROMPT}]},
                {"parts": [{"inline_data": {"mime_type": "image/png", "data": page_img}}]}
            ]
        }
    })

# Write JSONL
with open("batch_requests.jsonl", "w") as f:
    for req in requests:
        f.write(json.dumps(req) + "\n")

# Upload and create batch job
uploaded_file = client.files.upload(
    file='batch_requests.jsonl',
    config=types.UploadFileConfig(mime_type='jsonl')
)

batch_job = client.batches.create(
    model="gemini-3-flash-preview",
    src=uploaded_file.name,
    config={'display_name': "pdf-ocr-batch"}
)
```

**Best for:** Pre-processing document archives, overnight processing, cost-sensitive workloads.

### 1.4 Context Caching for System Prompts

Cache your OCR system prompt to save tokens on repeated calls:

```python
from google import genai
from google.genai import types

client = genai.Client()

# Create cache with OCR prompt (minimum 1024 tokens for Flash)
cache = client.caches.create(
    model='models/gemini-3-flash-preview',
    config=types.CreateCachedContentConfig(
        display_name='ocr-system-prompt',
        system_instruction=OCR_MASTER_PROMPT,  # Your detailed OCR instructions
        ttl="3600s"  # 1 hour TTL
    )
)

# Use cached prompt for all pages
for page in pages:
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=[page, "Extract text"],
        config=types.GenerateContentConfig(cached_content=cache.name)
    )
```

**Note:** Implicit caching is automatic - place large common content at the start of prompts.

---

## 2. Recommended Parameters

### 2.1 DPI Settings

| Use Case         | Recommended DPI | Image Size (A4) | Notes                       |
| ---------------- | --------------- | --------------- | --------------------------- |
| Fast processing  | 150             | ~1275x1755 px   | Good for clear printed text |
| **Standard OCR** | **200**         | ~1700x2338 px   | **Best balance**            |
| Handwriting      | 250             | ~2125x2923 px   | Current config              |
| Archival quality | 300             | ~2550x3508 px   | Overkill for OCR            |

**Recommendation:** Reduce from 250 to **200 DPI** for 20% faster processing with minimal quality loss.

### 2.2 Image Compression

| Format       | Size Reduction | Quality  | Recommendation                  |
| ------------ | -------------- | -------- | ------------------------------- |
| PNG          | 0%             | Lossless | Complex documents with graphics |
| **JPEG 85%** | **60-70%**     | High     | **Recommended for OCR**         |
| JPEG 70%     | 75-85%         | Medium   | Acceptable for clear text       |
| WebP         | 70-80%         | High     | Alternative to JPEG             |

**API Impact:** Smaller files = faster upload = lower latency.

```python
# Optimized image conversion
from PIL import Image
import io

def convert_page_optimized(pixmap, quality=85):
    img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

    # Resize if larger than needed
    max_dim = 2048
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue()
```

### 2.3 Optimal Batch Sizes

| Processing Mode | Batch Size | Concurrency | Notes               |
| --------------- | ---------- | ----------- | ------------------- |
| Sequential      | 1          | 1           | Simple but slow     |
| **Parallel**    | **5-10**   | **5-10**    | **Recommended**     |
| Aggressive      | 20+        | 20+         | Risk of rate limits |
| Batch API       | All pages  | N/A         | 24h turnaround      |

---

## 3. Code Patterns for Parallel Processing

### 3.1 Asyncio Pattern (Recommended)

```python
import asyncio
import aiohttp
from typing import List, Dict
import base64

class AsyncOCRProcessor:
    def __init__(self, api_key: str, max_concurrent: int = 5):
        self.api_key = api_key
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def process_page(self, session: aiohttp.ClientSession,
                           image_b64: str, page_num: int) -> Dict:
        """Process single page with rate limiting."""
        async with self.semaphore:
            payload = {
                "contents": [{
                    "parts": [
                        {"text": OCR_PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": image_b64}}
                    ]
                }],
                "generationConfig": {"temperature": 0}
            }

            url = f"{self.base_url}/models/gemini-2.5-flash:generateContent?key={self.api_key}"

            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                return {"page": page_num, "result": result}

    async def process_document(self, pages: List[str]) -> List[Dict]:
        """Process all pages in parallel with controlled concurrency."""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.process_page(session, page, i+1)
                for i, page in enumerate(pages)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

# Usage
processor = AsyncOCRProcessor(api_key="...", max_concurrent=5)
results = asyncio.run(processor.process_document(page_images))
```

### 3.2 ThreadPoolExecutor Pattern

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable
import threading

class ThreadedOCRProcessor:
    def __init__(self, ocr_function: Callable, max_workers: int = 5):
        self.ocr_function = ocr_function
        self.max_workers = max_workers
        self.results = {}
        self.lock = threading.Lock()

    def process_with_callback(self, pages: List[str],
                              on_complete: Callable = None) -> Dict:
        """Process pages with streaming results."""

        def process_and_notify(page_data):
            page_num, image = page_data
            result = self.ocr_function(image, page_num)

            with self.lock:
                self.results[page_num] = result

            if on_complete:
                on_complete(page_num, result)

            return page_num, result

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(process_and_notify, (i+1, page)): i
                for i, page in enumerate(pages)
            }

            # Stream results as they complete
            for future in as_completed(futures):
                page_num, result = future.result()
                yield page_num, result

# Usage with streaming
processor = ThreadedOCRProcessor(gemini_ocr, max_workers=5)

for page_num, result in processor.process_with_callback(pages):
    print(f"Page {page_num} complete!")
    # Update UI immediately
```

### 3.3 Producer-Consumer Pattern for Large PDFs

```python
import asyncio
from asyncio import Queue
from dataclasses import dataclass

@dataclass
class PageTask:
    page_num: int
    image_b64: str

@dataclass
class PageResult:
    page_num: int
    text: str
    success: bool

class ProducerConsumerOCR:
    def __init__(self, num_workers: int = 5):
        self.task_queue: Queue[PageTask] = Queue()
        self.result_queue: Queue[PageResult] = Queue()
        self.num_workers = num_workers

    async def producer(self, pdf_path: str):
        """Convert PDF pages and add to queue."""
        pages = convert_pdf_to_images(pdf_path)
        for i, page in enumerate(pages):
            await self.task_queue.put(PageTask(i+1, page))

        # Signal workers to stop
        for _ in range(self.num_workers):
            await self.task_queue.put(None)

    async def worker(self, worker_id: int, ocr_engine):
        """Process pages from queue."""
        while True:
            task = await self.task_queue.get()
            if task is None:
                break

            try:
                result = await ocr_engine.extract_async(task.image_b64)
                await self.result_queue.put(PageResult(
                    page_num=task.page_num,
                    text=result,
                    success=True
                ))
            except Exception as e:
                await self.result_queue.put(PageResult(
                    page_num=task.page_num,
                    text=str(e),
                    success=False
                ))

    async def consumer(self, total_pages: int, on_page_complete: Callable):
        """Stream results as they arrive."""
        completed = 0
        while completed < total_pages:
            result = await self.result_queue.get()
            on_page_complete(result)
            completed += 1

    async def run(self, pdf_path: str, ocr_engine, on_page_complete: Callable):
        """Run full pipeline."""
        total_pages = get_page_count(pdf_path)

        await asyncio.gather(
            self.producer(pdf_path),
            *[self.worker(i, ocr_engine) for i in range(self.num_workers)],
            self.consumer(total_pages, on_page_complete)
        )
```

---

## 4. Gemini API Specific Optimizations

### 4.1 Multiple Images in Single Request

Gemini supports up to **3,600 images** per request:

```python
# Process multiple pages in single API call
from google import genai
from google.genai import types

client = genai.Client()

# Batch pages together (2-4 pages per request)
def batch_pages(pages: List[str], batch_size: int = 3):
    for i in range(0, len(pages), batch_size):
        yield pages[i:i+batch_size]

for batch in batch_pages(page_images, batch_size=3):
    contents = [OCR_PROMPT]
    for i, img in enumerate(batch):
        contents.append(types.Part.from_bytes(data=img, mime_type='image/png'))
        contents.append(f"[PAGE {i+1}]")

    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=contents
    )
```

**Tradeoff:** Larger batches = fewer API calls but longer latency per call.

### 4.2 Token Calculation Deep Dive

For images:

- **≤384px both dimensions:** 258 tokens fixed
- **>384px:** Tiled into 768x768 tiles, each = 258 tokens
- Formula: `tiles = ceil(width/crop_unit) × ceil(height/crop_unit)` where `crop_unit = floor(min(width, height) / 1.5)`

**Optimal image size:** Keep images around **768-1024px** max dimension to minimize tiles.

```python
def optimal_resize(image: Image, max_dim: int = 1024):
    """Resize to minimize token usage while preserving quality."""
    width, height = image.size

    if max(width, height) <= 384:
        return image  # Single tile, no resize needed

    # Target: 1-2 tiles maximum
    if max(width, height) > max_dim:
        ratio = max_dim / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    return image
```

### 4.3 Use Files API for Reusable Content

```python
# Upload once, use multiple times
uploaded_pdf = client.files.upload(file='large_doc.pdf')

# Multiple queries on same document
questions = ["Extract all names", "Find dates", "Summarize tables"]

for question in questions:
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=[uploaded_pdf, question]
    )
```

### 4.4 Structured Output for Consistent Parsing

```python
from pydantic import BaseModel
from typing import List

class OCRBlock(BaseModel):
    block_id: int
    type: str
    text: str
    confidence: str

class OCRResult(BaseModel):
    page_number: int
    blocks: List[OCRBlock]
    full_text: str

config = types.GenerateContentConfig(
    response_mime_type='application/json',
    response_schema=OCRResult
)
```

---

## 5. How NotebookLM Achieves Fast Processing

Based on public information, NotebookLM likely uses:

1. **Native PDF Processing:** Direct PDF upload to Gemini without image conversion
2. **Long Context Window:** Process entire documents at once (Gemini supports 1M+ tokens)
3. **Incremental Processing:** Parse structure first, extract details on demand
4. **Aggressive Caching:** Cache processed documents for repeat access
5. **Background Indexing:** Pre-process and index while user reviews
6. **Smart Chunking:** Semantic document segmentation, not page-by-page

---

## 6. Implementation Recommendations for PerfectOCR

### Immediate Optimizations (Low Effort, High Impact)

1. **Switch to native PDF upload:**

   ```python
   # Instead of converting to images, upload PDF directly
   uploaded_pdf = client.files.upload(file=pdf_path)
   response = client.models.generate_content(
       model='gemini-3-flash-preview',
       contents=[uploaded_pdf, OCR_PROMPT]
   )
   ```

2. **Add media_resolution parameter:**

   ```python
   config = types.GenerateContentConfig(
       media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
   )
   ```

3. **Reduce DPI from 250 to 200**

4. **Switch to JPEG compression (quality=85)**

### Medium-Term Improvements

1. **Implement parallel processing with asyncio** (see pattern above)

2. **Add context caching for OCR prompt:**

   ```python
   cache = client.caches.create(
       model='models/gemini-3-flash-preview',
       config=types.CreateCachedContentConfig(
           system_instruction=MASTER_PROMPT,
           ttl="3600s"
       )
   )
   ```

3. **Hybrid approach:** Use Tesseract for simple pages, AI for complex

### Long-Term Optimizations

1. **Implement Batch API** for cost savings on large volume processing

2. **Add intelligent page classification:**
   - Text-only pages → Tesseract
   - Mixed/complex pages → Gemini
   - Tables/forms → Higher resolution

3. **Implement streaming results:**
   ```python
   async for page_num, result in processor.stream_results():
       yield result  # Return to UI immediately
   ```

---

## 7. Expected Performance

With all optimizations applied:

| Scenario            | Current (Est.) | Optimized         | Improvement |
| ------------------- | -------------- | ----------------- | ----------- |
| PDF→Images          | 0.5s/page      | 0s (native)       | 100%        |
| API Call            | 3-5s/page      | 2-3s/page         | 40%         |
| Total (sequential)  | 4-6s/page      | 2-3s/page         | 50%         |
| Total (parallel 5x) | 4-6s/page      | **0.4-0.6s/page** | **90%**     |
| 100-page PDF        | 6-10 min       | **1-2 min**       | 80%         |

---

## 8. Quick Reference Code Snippets

### Optimal Configuration

```python
# config.py optimizations
DPI = 200  # Reduced from 250
IMAGE_FORMAT = "jpeg"
JPEG_QUALITY = 85
MAX_CONCURRENT_REQUESTS = 5
USE_NATIVE_PDF = True
MEDIA_RESOLUTION = "MEDIUM"
ENABLE_CONTEXT_CACHING = True
CACHE_TTL = 3600  # 1 hour
```

### Complete Optimized Pipeline

```python
import asyncio
from google import genai
from google.genai import types
from pathlib import Path

class OptimizedOCRPipeline:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.prompt_cache = None

    async def initialize_cache(self, system_prompt: str):
        """Initialize cached system prompt."""
        self.prompt_cache = self.client.caches.create(
            model='models/gemini-3-flash-preview',
            config=types.CreateCachedContentConfig(
                system_instruction=system_prompt,
                ttl="3600s"
            )
        )

    async def process_pdf_native(self, pdf_path: Path) -> str:
        """Process PDF using native upload (fastest method)."""
        uploaded = self.client.files.upload(
            file=str(pdf_path),
            config=dict(mime_type='application/pdf')
        )

        config = types.GenerateContentConfig(
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
            cached_content=self.prompt_cache.name if self.prompt_cache else None
        )

        response = self.client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=[uploaded, "Extract all text with structure"],
            config=config
        )

        return response.text

    async def process_images_parallel(self,
                                       images: list,
                                       max_concurrent: int = 5) -> list:
        """Process images in parallel with rate limiting."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_one(img_data: bytes, page_num: int):
            async with semaphore:
                response = self.client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=[
                        types.Part.from_bytes(data=img_data, mime_type='image/jpeg'),
                        "Extract text"
                    ]
                )
                return {"page": page_num, "text": response.text}

        tasks = [process_one(img, i+1) for i, img in enumerate(images)]
        return await asyncio.gather(*tasks)
```

---

## References

1. [Gemini API Image Understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
2. [Gemini Batch API](https://ai.google.dev/gemini-api/docs/batch-api)
3. [Context Caching](https://ai.google.dev/gemini-api/docs/caching)
4. [Media Resolution Guide](https://ai.google.dev/gemini-api/docs/media-resolution)
5. [Document Processing](https://ai.google.dev/gemini-api/docs/document-processing)
6. [Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)

---

_Document generated: March 4, 2026_
_Based on Gemini API documentation and best practices research_
