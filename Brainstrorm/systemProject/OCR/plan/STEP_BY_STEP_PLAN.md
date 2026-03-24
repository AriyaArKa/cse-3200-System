# Step-by-Step Implementation Plan

> From present situation → Full sophisticated document intelligence system
> Backend first → Streamlit for testing → Frontend later
> Each step is small, testable, and builds on the previous one

---

## PRESENT SITUATION (What You Have Now)

```
PDF Upload → pdf2image (300 DPI) → Gemini 2.5 Flash OCR → Raw JSON → Merged JSON
```

**What works:**

- PDF → image conversion (pdf.py)
- Gemini 2.5 Flash OCR — extracts Bangla + English text accurately
- Raw JSON output per page, merged into one file
- Streamlit UI for upload + display

**What's missing:**

- No chunking / embedding / vector search
- No document classification
- No card template filling
- No regeneration
- No confidence scoring
- No cost optimization
- No image-aware extraction

---

## PHASE 1: OCR Enhancement (Steps 1-3)

### Step 1: Improve OCR Prompt for Images & Mixed Content

**Goal:** Gemini 2.5 Flash already gives good Bangla results. Enhance the prompt so it also properly identifies images, logos, signatures, seals relative to the text.

**Present file:** `app.py` → `ocr_image()` function

**What to do:**

```python
# NEW ocr_image prompt — replace current prompt in app.py
OCR_PROMPT = """You are a document OCR system. Extract ALL content from this image.

RULES:
1. Extract ALL text EXACTLY as written. Do NOT translate Bangla to English or vice versa.
2. Preserve original Bangla characters (বাংলা) exactly as they appear.
3. For IMAGES/LOGOS/PHOTOS in the document:
   - Identify them with type: "image", "logo", "signature", "seal", "photo", "stamp"
   - Describe what the image shows in 1-2 sentences
   - Give approximate position: "top-left", "top-center", "top-right", "bottom-left", etc.
4. For TABLES: preserve exact row/column structure
5. For SIGNATURES: note the name (if legible) and position

Return STRICT valid JSON with this structure:
{
  "page_content": [
    {"type": "header|title|paragraph|table|list|image|signature|seal|logo|stamp",
     "content": "...",
     "position": "top|middle|bottom",
     "language": "bangla|english|mixed"}
  ],
  "detected_images": [
    {"type": "logo|signature|seal|photo|stamp",
     "description": "...",
     "position": "top-left|top-center|..."}
  ],
  "metadata": {
    "has_bangla": true/false,
    "has_english": true/false,
    "has_tables": true/false,
    "has_images": true/false
  }
}

Do NOT include markdown formatting. Do NOT include explanations outside JSON.
Ensure UTF-8 correctness."""
```

**Test with:** Upload a PDF that has logos, signatures, tables, and Bangla text. Compare old vs. new output.

**Files to change:** `app.py` (update `ocr_image` function)  
**New files:** None  
**Estimated time:** 1-2 hours

---

### Step 2: Create Structured OCR Output Module

**Goal:** Separate OCR logic into its own module. Parse and validate the Gemini response into a clean Python object.

**New file:** `ocr_engine.py`

````python
# ocr_engine.py
import json
import re
from PIL import Image
from google import genai
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DetectedImage:
    type: str              # logo, signature, seal, photo, stamp
    description: str
    position: str

@dataclass
class ContentBlock:
    type: str              # header, title, paragraph, table, list, image, signature
    content: str
    position: str = "middle"
    language: str = "mixed"

@dataclass
class PageOCRResult:
    page_number: int
    content_blocks: List[ContentBlock]
    detected_images: List[DetectedImage]
    has_bangla: bool = False
    has_english: bool = False
    has_tables: bool = False
    has_images: bool = False
    raw_json: dict = field(default_factory=dict)
    ocr_confidence: float = 0.85  # Gemini default

class OCREngine:
    """Wrapper around Gemini 2.5 Flash for OCR."""

    OCR_PROMPT = """..."""  # (the full prompt from Step 1)

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def extract_page(self, image_path: str, page_number: int) -> PageOCRResult:
        """OCR a single page image → structured PageOCRResult."""
        image = Image.open(image_path)
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[self.OCR_PROMPT, image],
        )
        raw_text = response.text
        parsed = self._parse_response(raw_text)
        return self._build_result(parsed, page_number)

    def _parse_response(self, text: str) -> dict:
        """Clean markdown fences, parse JSON."""
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"page_content": [{"type": "paragraph", "content": text}],
                    "detected_images": [], "metadata": {}}

    def _build_result(self, data: dict, page_number: int) -> PageOCRResult:
        """Convert raw dict → PageOCRResult dataclass."""
        blocks = []
        for item in data.get("page_content", []):
            blocks.append(ContentBlock(
                type=item.get("type", "paragraph"),
                content=item.get("content", ""),
                position=item.get("position", "middle"),
                language=item.get("language", "mixed"),
            ))

        images = []
        for img in data.get("detected_images", []):
            images.append(DetectedImage(
                type=img.get("type", "image"),
                description=img.get("description", ""),
                position=img.get("position", "unknown"),
            ))

        meta = data.get("metadata", {})
        return PageOCRResult(
            page_number=page_number,
            content_blocks=blocks,
            detected_images=images,
            has_bangla=meta.get("has_bangla", False),
            has_english=meta.get("has_english", False),
            has_tables=meta.get("has_tables", False),
            has_images=meta.get("has_images", False),
            raw_json=data,
        )
````

**Test with:** Same PDFs. Verify `PageOCRResult` objects are created correctly.

**Files to change:** `app.py` (import and use `OCREngine` instead of raw `ocr_image()`)  
**New files:** `ocr_engine.py`  
**Estimated time:** 2-3 hours

---

### Step 3: Multi-Page Document Assembly

**Goal:** Combine all page results into one `DocumentOCRResult` that represents the full document.

**Add to `ocr_engine.py`:**

```python
@dataclass
class DocumentOCRResult:
    filename: str
    total_pages: int
    pages: List[PageOCRResult]
    all_text: str = ""           # concatenated full text for search
    detected_languages: List[str] = field(default_factory=list)
    total_images: int = 0

    def __post_init__(self):
        # Build concatenated text for downstream chunking
        texts = []
        langs = set()
        img_count = 0
        for page in self.pages:
            for block in page.content_blocks:
                if block.type not in ("image", "logo", "seal", "stamp"):
                    texts.append(block.content)
                if block.language:
                    langs.add(block.language)
            img_count += len(page.detected_images)
        self.all_text = "\n\n".join(texts)
        self.detected_languages = list(langs)
        self.total_images = img_count

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "filename": self.filename,
            "total_pages": self.total_pages,
            "detected_languages": self.detected_languages,
            "total_images": self.total_images,
            "pages": [
                {
                    "page_number": p.page_number,
                    "content_blocks": [
                        {"type": b.type, "content": b.content,
                         "position": b.position, "language": b.language}
                        for b in p.content_blocks
                    ],
                    "detected_images": [
                        {"type": img.type, "description": img.description,
                         "position": img.position}
                        for img in p.detected_images
                    ],
                    "metadata": {
                        "has_bangla": p.has_bangla,
                        "has_english": p.has_english,
                        "has_tables": p.has_tables,
                        "has_images": p.has_images,
                    }
                }
                for p in self.pages
            ],
        }
```

**Test:** Upload multi-page PDF, verify `DocumentOCRResult.all_text` contains full concatenated text. Verify `to_dict()` serializes properly.

**Files to change:** `ocr_engine.py`  
**Estimated time:** 1-2 hours

---

## PHASE 2: Chunking & Embedding (Steps 4-7)

### Step 4: Text Chunker — Split OCR Output into Semantic Chunks

**Goal:** Split the extracted text into chunks suitable for embedding. Respect section boundaries from OCR output.

**New file:** `chunker.py`

**Strategy:** Use the structured OCR output (which already has type=header, paragraph, table, list) as natural section boundaries. Each content block is either one chunk or split further if too long.

```python
# chunker.py
from dataclasses import dataclass, field
from typing import List
import re
import uuid

@dataclass
class Chunk:
    chunk_id: str
    content: str
    chunk_type: str        # header, paragraph, table, list, image_desc
    page_number: int
    token_count: int
    metadata: dict = field(default_factory=dict)

class DocumentChunker:
    """Splits OCR output into semantic chunks."""

    MAX_TOKENS = 512
    OVERLAP_TOKENS = 64

    def chunk_document(self, doc_result) -> List[Chunk]:
        """Take DocumentOCRResult → List[Chunk]"""
        chunks = []

        for page in doc_result.pages:
            for block in page.content_blocks:
                content = block.content
                if isinstance(content, list):
                    content = "\n".join(content)
                if not content or not content.strip():
                    continue

                token_count = self._count_tokens(content)

                if token_count <= self.MAX_TOKENS:
                    # Single chunk
                    chunks.append(Chunk(
                        chunk_id=uuid.uuid4().hex[:12],
                        content=content,
                        chunk_type=block.type,
                        page_number=page.page_number,
                        token_count=token_count,
                        metadata={
                            "language": block.language,
                            "position": block.position,
                            "has_bangla": page.has_bangla,
                            "has_tables": page.has_tables,
                        }
                    ))
                else:
                    # Split large block with overlap
                    sub_chunks = self._split_with_overlap(
                        content, block.type, page.page_number, block.language
                    )
                    chunks.extend(sub_chunks)

            # Also add image descriptions as chunks (for contextual search)
            for img in page.detected_images:
                if img.description:
                    chunks.append(Chunk(
                        chunk_id=uuid.uuid4().hex[:12],
                        content=f"[{img.type.upper()}] {img.description}",
                        chunk_type="image_description",
                        page_number=page.page_number,
                        token_count=self._count_tokens(img.description),
                        metadata={"image_type": img.type, "position": img.position}
                    ))

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Approximate token count. ~1 token per 4 chars for English,
        ~1 token per 2 chars for Bangla."""
        bangla_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        english_chars = len(text) - bangla_chars
        return (bangla_chars // 2) + (english_chars // 4) + 1

    def _split_with_overlap(self, text, block_type, page_num, language) -> List[Chunk]:
        """Split text into overlapping chunks by sentence boundaries."""
        sentences = re.split(r'(?<=[।.!?\n])\s*', text)
        chunks = []
        current = []
        current_tokens = 0

        for sentence in sentences:
            sent_tokens = self._count_tokens(sentence)
            if current_tokens + sent_tokens > self.MAX_TOKENS and current:
                chunk_text = " ".join(current)
                chunks.append(Chunk(
                    chunk_id=uuid.uuid4().hex[:12],
                    content=chunk_text,
                    chunk_type=block_type,
                    page_number=page_num,
                    token_count=current_tokens,
                    metadata={"language": language, "is_split": True}
                ))
                # Overlap: keep last few sentences
                overlap_tokens = 0
                overlap = []
                for s in reversed(current):
                    t = self._count_tokens(s)
                    if overlap_tokens + t > self.OVERLAP_TOKENS:
                        break
                    overlap.insert(0, s)
                    overlap_tokens += t
                current = overlap
                current_tokens = overlap_tokens

            current.append(sentence)
            current_tokens += sent_tokens

        if current:
            chunk_text = " ".join(current)
            chunks.append(Chunk(
                chunk_id=uuid.uuid4().hex[:12],
                content=chunk_text,
                chunk_type=block_type,
                page_number=page_num,
                token_count=current_tokens,
                metadata={"language": language, "is_split": bool(chunks)}
            ))

        return chunks
```

**Test in Streamlit:** After OCR, show chunk count and list of chunks with their types and token counts.

**Files:** `chunker.py` (new)  
**Estimated time:** 2-3 hours

---

### Step 5: FREE Embedding with Sentence-Transformers

**Goal:** Generate embeddings for each chunk. Completely free, runs locally.

**Install:**

```bash
pip install sentence-transformers
```

**New file:** `embedder.py`

```python
# embedder.py
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

class EmbeddingService:
    """Free local embedding using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Model options (all FREE, all local):
        - "all-MiniLM-L6-v2"        → 384 dim, fast, good for English
        - "paraphrase-multilingual-MiniLM-L12-v2"  → 384 dim, BEST for Bangla+English
        - "all-mpnet-base-v2"       → 768 dim, best quality English

        RECOMMENDED: "paraphrase-multilingual-MiniLM-L12-v2" (supports 50+ languages including Bangla)
        """
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text → vector."""
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed multiple texts efficiently → list of vectors."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True
        )
        return embeddings.tolist()

    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

> **Why `paraphrase-multilingual-MiniLM-L12-v2`?**
>
> - Free, local, no API costs ever
> - Supports Bangla natively (trained on 50+ languages)
> - 384 dimensions (compact, fast)
> - Decent quality for semantic search

**Test:** Embed a Bangla sentence and an English sentence, check that similarity between related content is high.

**Files:** `embedder.py` (new)  
**Estimated time:** 1-2 hours

---

### Step 6: Vector Database with Pinecone (Free Tier)

**Goal:** Store chunks + embeddings in Pinecone for fast similarity search.

**Pinecone Free Tier:**

- 1 index
- 100K vectors (more than enough for hundreds of documents)
- 1 project
- No credit card required

**Install:**

```bash
pip install pinecone
```

**New file:** `vector_store.py`

```python
# vector_store.py
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class VectorStore:
    """Pinecone vector database for chunk storage and retrieval."""

    def __init__(self):
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index_name = "doc-intelligence"
        self.dimension = 384  # matches multilingual-MiniLM
        self._ensure_index()

    def _ensure_index(self):
        """Create index if it doesn't exist."""
        existing = [idx.name for idx in self.pc.list_indexes()]
        if self.index_name not in existing:
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        self.index = self.pc.Index(self.index_name)

    def upsert_chunks(self, document_id: str, chunks: list, embeddings: list):
        """Store chunks with embeddings and metadata in Pinecone."""
        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            vectors.append({
                "id": f"{document_id}_{chunk.chunk_id}",
                "values": embedding,
                "metadata": {
                    "document_id": document_id,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content[:1000],  # Pinecone metadata limit
                    "chunk_type": chunk.chunk_type,
                    "page_number": chunk.page_number,
                    "language": chunk.metadata.get("language", "mixed"),
                    "has_bangla": chunk.metadata.get("has_bangla", False),
                }
            })

        # Upsert in batches of 100
        for i in range(0, len(vectors), 100):
            batch = vectors[i:i+100]
            self.index.upsert(vectors=batch)

    def search(self, query_embedding: list, document_id: str = None,
               top_k: int = 5, filter_dict: dict = None) -> List[Dict]:
        """Search for similar chunks."""
        filters = {}
        if document_id:
            filters["document_id"] = {"$eq": document_id}
        if filter_dict:
            filters.update(filter_dict)

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filters if filters else None
        )

        return [
            {
                "chunk_id": match.metadata.get("chunk_id"),
                "content": match.metadata.get("content"),
                "score": match.score,
                "page_number": match.metadata.get("page_number"),
                "chunk_type": match.metadata.get("chunk_type"),
            }
            for match in results.matches
        ]

    def delete_document(self, document_id: str):
        """Delete all chunks for a document."""
        # Pinecone requires listing IDs first with metadata filter
        self.index.delete(filter={"document_id": {"$eq": document_id}})

    def get_index_stats(self) -> dict:
        """Get index statistics."""
        return self.index.describe_index_stats()
```

> **Alternative: ChromaDB (100% local, no account needed)**
> If you don't want to create a Pinecone account, use ChromaDB instead:
>
> ```bash
> pip install chromadb
> ```
>
> I'll provide a ChromaDB alternative in Step 6B below.

---

### Step 6B: Alternative — ChromaDB (Fully Local, Zero Cost)

**For those who prefer no external service:**

```python
# vector_store_chroma.py
import chromadb
from typing import List, Dict

class VectorStoreChroma:
    """ChromaDB — fully local, no API key needed."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="doc_chunks",
            metadata={"hnsw:space": "cosine"}
        )

    def upsert_chunks(self, document_id: str, chunks: list, embeddings: list):
        """Store chunks."""
        ids = [f"{document_id}_{c.chunk_id}" for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "chunk_type": c.chunk_type,
                "page_number": c.page_number,
                "language": c.metadata.get("language", "mixed"),
            }
            for c in chunks
        ]
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list, document_id: str = None,
               top_k: int = 5) -> List[Dict]:
        """Search similar chunks."""
        where_filter = {"document_id": document_id} if document_id else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "score": 1 - results["distances"][0][i],  # distance → similarity
                "page_number": results["metadatas"][0][i].get("page_number"),
                "chunk_type": results["metadatas"][0][i].get("chunk_type"),
            })
        return output

    def delete_document(self, document_id: str):
        """Delete all chunks for a document."""
        # Get all IDs with this document_id
        results = self.collection.get(where={"document_id": document_id})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
```

**Test:** Store 10 chunks, query with a Bangla sentence, verify top results are semantically related.

**Files:** `vector_store.py` (Pinecone) OR `vector_store_chroma.py` (ChromaDB)  
**Estimated time:** 2-3 hours

---

### Step 7: BM25 Search + Hybrid Search (BM25 + Cosine)

**Goal:** Implement both keyword search (BM25) and semantic search (cosine), then combine them for hybrid search. This gives much better results than either alone.

**Install:**

```bash
pip install rank-bm25
```

**New file:** `search_engine.py`

```python
# search_engine.py
from rank_bm25 import BM25Okapi
from typing import List, Dict, Tuple
import re
import numpy as np

class SearchEngine:
    """
    Hybrid search: BM25 (keyword) + Cosine Similarity (semantic).

    Why hybrid?
    - BM25 is excellent for exact keyword matches (e.g., "স্মারক নং" → finds exact memo number)
    - Cosine similarity finds semantically related content (e.g., "deadline" → finds "শেষ তারিখ")
    - Combined = best of both worlds
    """

    def __init__(self, embedder):
        self.embedder = embedder
        self.bm25 = None
        self.chunks = []
        self.tokenized_corpus = []

    def index_chunks(self, chunks: list):
        """Build BM25 index from chunks."""
        self.chunks = chunks
        self.tokenized_corpus = [self._tokenize(c.content) for c in chunks]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization that works for Bangla + English."""
        # Split on whitespace and punctuation, keep Bangla characters
        tokens = re.findall(r'[\u0980-\u09FF]+|[a-zA-Z0-9]+', text.lower())
        return tokens

    def bm25_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Pure keyword search using BM25."""
        if not self.bm25:
            return []
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "chunk_id": self.chunks[idx].chunk_id,
                    "content": self.chunks[idx].content,
                    "score": float(scores[idx]),
                    "page_number": self.chunks[idx].page_number,
                    "chunk_type": self.chunks[idx].chunk_type,
                    "search_method": "bm25",
                })
        return results

    def cosine_search(self, query: str, vector_store, document_id: str,
                      top_k: int = 10) -> List[Dict]:
        """Pure semantic search using embeddings + vector DB."""
        query_embedding = self.embedder.embed_text(query)
        results = vector_store.search(query_embedding, document_id, top_k)
        for r in results:
            r["search_method"] = "cosine"
        return results

    def hybrid_search(self, query: str, vector_store, document_id: str,
                      top_k: int = 5, bm25_weight: float = 0.3,
                      cosine_weight: float = 0.7) -> List[Dict]:
        """
        Hybrid search: combines BM25 + cosine similarity.

        Weights:
        - bm25_weight=0.3  → keyword matching (good for exact terms, numbers, names)
        - cosine_weight=0.7 → semantic matching (good for meaning, Bangla-English cross-lingual)

        Use cases where BM25 excels:
        - "স্মারক নং-খুপ্রবি/প্রশা/ ৪৫০৭/৭০" → exact memo number match
        - "রেজিস্ট্রার" → exact name match

        Use cases where cosine excels:
        - "who signed this?" → finds signature blocks even if "signed" isn't in text
        - "application deadline" → finds "আবেদনের শেষ তারিখ" (Bangla equivalent)
        """
        bm25_results = self.bm25_search(query, top_k=top_k * 2)
        cosine_results = self.cosine_search(query, vector_store, document_id, top_k=top_k * 2)

        # Normalize scores to 0-1 range
        bm25_scores = self._normalize_scores(bm25_results)
        cosine_scores = self._normalize_scores(cosine_results)

        # Merge by chunk_id with weighted scores
        combined = {}
        for r in bm25_scores:
            cid = r["chunk_id"]
            combined[cid] = {
                **r,
                "final_score": r["score"] * bm25_weight,
                "bm25_score": r["score"],
                "cosine_score": 0.0
            }

        for r in cosine_scores:
            cid = r["chunk_id"]
            if cid in combined:
                combined[cid]["final_score"] += r["score"] * cosine_weight
                combined[cid]["cosine_score"] = r["score"]
                combined[cid]["search_method"] = "hybrid"
            else:
                combined[cid] = {
                    **r,
                    "final_score": r["score"] * cosine_weight,
                    "bm25_score": 0.0,
                    "cosine_score": r["score"],
                    "search_method": "hybrid",
                }

        # Sort by final_score, return top_k
        sorted_results = sorted(combined.values(), key=lambda x: x["final_score"], reverse=True)
        return sorted_results[:top_k]

    def _normalize_scores(self, results: List[Dict]) -> List[Dict]:
        """Normalize scores to 0-1 range."""
        if not results:
            return results
        max_score = max(r["score"] for r in results)
        if max_score == 0:
            return results
        for r in results:
            r["score"] = r["score"] / max_score
        return results
```

**Test in Streamlit:**

- Search a Bangla keyword like "বিজ্ঞপ্তি" → BM25 should find exact match
- Search "what is the notice about?" → cosine should find Bangla content
- Hybrid should combine both and give best results

**Files:** `search_engine.py` (new)  
**Estimated time:** 3-4 hours

---

## PHASE 3: Document Classification & Card Filling (Steps 8-11)

### Step 8: Document Type Classifier

**Goal:** Automatically classify the uploaded document into one of the 5 PDF types defined in `pdftypes.txt`.

**New file:** `classifier.py`

```python
# classifier.py
import json
from typing import Tuple
from pathlib import Path

class DocumentClassifier:
    """Classify document into one of the 5 PDF types."""

    def __init__(self, embedder, pdftypes_path: str = "pdftypes.txt"):
        self.embedder = embedder
        self.pdf_types = self._load_types(pdftypes_path)
        # Pre-compute embeddings for each category's keywords
        self._type_embeddings = {}
        for ptype in self.pdf_types:
            keywords = " ".join(ptype["real_life_examples"]) + " " + " ".join(ptype["common_fields"])
            self._type_embeddings[ptype["id"]] = self.embedder.embed_text(keywords)

    def _load_types(self, path: str) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        return data["pdf_types"]

    def classify(self, document_text: str) -> Tuple[str, str, float]:
        """
        Classify document text → (type_id, category_name, confidence)

        Method: Embed the full document text, compare cosine similarity
        against each category's keyword embedding.
        """
        # Use first 2000 chars for classification (enough to determine type)
        sample = document_text[:2000]
        doc_embedding = self.embedder.embed_text(sample)

        best_id = None
        best_category = None
        best_score = -1

        for ptype in self.pdf_types:
            type_emb = self._type_embeddings[ptype["id"]]
            score = self.embedder.similarity(doc_embedding, type_emb)
            if score > best_score:
                best_score = score
                best_id = ptype["id"]
                best_category = ptype["category"]

        return best_id, best_category, best_score

    def get_common_fields(self, type_id: str) -> list:
        """Get expected fields for a document type."""
        for ptype in self.pdf_types:
            if ptype["id"] == type_id:
                return ptype["common_fields"]
        return []
```

**Test:** Upload a university notice → should classify as PDF001. Upload a job circular → PDF003.

**Files:** `classifier.py` (new)  
**Estimated time:** 1-2 hours

---

### Step 9: Card Template Manager

**Goal:** Load the correct card template based on document type. Initialize empty card.

**New file:** `card_manager.py`

```python
# card_manager.py
import json
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class CardField:
    field_id: str
    title: str
    field_type: str       # ai_summary, text, list, date, table, checklist, etc.
    value: str = ""
    confidence: float = 0.0
    source: str = "empty"  # empty, ai_extracted, user_edited, regenerated
    editable: bool = True
    regeneratable: bool = False

@dataclass
class Card:
    card_id: str
    template_id: str
    template_name: str
    document_id: str
    fields: List[CardField]
    overall_score: float = 0.0
    status: str = "draft"   # draft, filled, reviewed

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "document_id": self.document_id,
            "overall_score": self.overall_score,
            "status": self.status,
            "fields": [
                {
                    "field_id": f.field_id,
                    "title": f.title,
                    "type": f.field_type,
                    "value": f.value,
                    "confidence": f.confidence,
                    "source": f.source,
                    "editable": f.editable,
                    "regeneratable": f.regeneratable,
                }
                for f in self.fields
            ],
        }

class CardTemplateManager:
    """Manages card templates and creates card instances."""

    # Mapping: PDF type category → card template ID
    TYPE_TO_TEMPLATE = {
        "University Notice": "student_support_card",
        "Government Circular / Office Order": "government_policy_impact_card",
        "Job & Recruitment Document": "job_eligibility_checker_card",
        "Financial & Banking Document": "financial_health_card",
        "Official Meeting & Administrative Documents": "meeting_decision_tracker_card",
    }

    def __init__(self, templates_path: str = "templateStructure.txt"):
        self.templates = self._load_templates(templates_path)

    def _load_templates(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        return {t["id"]: t for t in data["card_templates"]}

    def get_template_for_type(self, category: str) -> Optional[str]:
        """Get template ID for a PDF type category."""
        return self.TYPE_TO_TEMPLATE.get(category)

    def create_card(self, template_id: str, document_id: str) -> Card:
        """Create an empty card from a template."""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        fields = []
        for section in template["sections"]:
            fields.append(CardField(
                field_id=section["section_id"],
                title=section["title"],
                field_type=section["type"],
                editable=section.get("editable", True),
                regeneratable=section.get("regeneratable", False),
            ))

        return Card(
            card_id=uuid.uuid4().hex[:12],
            template_id=template_id,
            template_name=template["name"],
            document_id=document_id,
            fields=fields,
        )
```

**Test:** Classify document → get template ID → create empty card → display in Streamlit.

**Files:** `card_manager.py` (new)  
**Estimated time:** 1-2 hours

---

### Step 10: Card Filler — LLM Post-Processing

**Goal:** Use hybrid search to find relevant chunks, then use LLM to fill each card field.

**New file:** `card_filler.py`

```python
# card_filler.py
import json
import re
from typing import List, Dict
from google import genai

class CardFiller:
    """Fills card fields using search results + LLM post-processing."""

    # Query templates: field_id → search query
    # These map each card field to the best search query to find relevant content
    FIELD_QUERIES = {
        # Student Support Card
        "what_is_this_about": "বিজ্ঞপ্তি সম্পর্কে মূল বিষয় notice about summary",
        "who_is_affected": "কারা প্রভাবিত affected students department applicable",
        "what_you_must_do": "করণীয় নির্দেশনা instructions action required must do",
        "important_deadlines": "তারিখ সময়সীমা deadline date important",
        "risk_if_ignored": "শাস্তি ঝুঁকি risk penalty consequence ignore",

        # Job Eligibility Card
        "job_summary": "পদের নাম বিবরণ job position overview summary",
        "eligibility_checklist": "যোগ্যতা শিক্ষাগত অভিজ্ঞতা qualification eligibility requirement",
        "documents_required": "প্রয়োজনীয় কাগজপত্র documents required papers",
        "application_steps": "আবেদন প্রক্রিয়া application process steps how to apply",
        "deadline_alert": "আবেদনের শেষ তারিখ application deadline last date",

        # Government Policy Card
        "policy_summary": "নীতি আদেশ সারসংক্ষেপ policy order summary",
        "who_is_impacted": "কারা প্রভাবিত impacted affected persons",
        "what_changes": "পরিবর্তন changes before after difference",
        "actions_required": "পদক্ষেপ action required citizen",
        "effective_date": "কার্যকর তারিখ effective date",

        # Financial Card
        "financial_summary": "মোট আয় ব্যয় total income expense balance summary",
        "spending_analysis": "খরচ বিশ্লেষণ spending pattern analysis",
        "risk_alert": "ঝুঁকি alert risk overdraft warning",
        "savings_suggestion": "সঞ্চয় পরামর্শ savings suggestion improvement",

        # Meeting Card
        "meeting_summary": "সভা সারসংক্ষেপ meeting summary agenda",
        "decisions_taken": "সিদ্ধান্ত decision taken resolved",
        "responsibility_matrix": "দায়িত্ব responsibility task assigned person deadline",
        "follow_up_reminder": "ফলো-আপ follow-up next meeting reminder",
    }

    def __init__(self, api_key: str, search_engine, vector_store, embedder):
        self.client = genai.Client(api_key=api_key)
        self.search = search_engine
        self.vector_store = vector_store
        self.embedder = embedder

    def fill_card(self, card, document_id: str) -> None:
        """Fill all fields of a card using search + LLM."""
        for field in card.fields:
            self._fill_field(field, document_id)

        # Calculate overall score
        scores = [f.confidence for f in card.fields if f.confidence > 0]
        card.overall_score = sum(scores) / len(scores) if scores else 0.0
        card.status = "filled"

    def _fill_field(self, field, document_id: str):
        """Fill a single field."""
        # Step 1: Get search query for this field
        query = self.FIELD_QUERIES.get(field.field_id, field.title)

        # Step 2: Hybrid search for relevant chunks
        results = self.search.hybrid_search(
            query=query,
            vector_store=self.vector_store,
            document_id=document_id,
            top_k=3,
        )

        if not results:
            field.value = "তথ্য পাওয়া যায়নি / No information found"
            field.confidence = 0.1
            field.source = "no_data"
            return

        # Step 3: Try rule-based extraction first (free!)
        context = "\n".join([r["content"] for r in results])
        rule_result = self._try_rule_based(field, context)
        if rule_result:
            field.value = rule_result
            field.confidence = 0.9
            field.source = "rule_based"
            return

        # Step 4: Use LLM for complex fields
        llm_result = self._llm_extract(field, context)
        field.value = llm_result
        field.confidence = 0.8
        field.source = "ai_extracted"

    def _try_rule_based(self, field, context: str):
        """Try extracting with regex patterns — FREE, no API cost."""
        if field.field_type == "date":
            # Match Bangla dates: ০৫/০২/২০২৩ or 05/02/2023
            dates = re.findall(
                r'[০-৯\d]{1,2}[/-][০-৯\d]{1,2}[/-][০-৯\d]{2,4}', context
            )
            if dates:
                return ", ".join(dates)

        if field.field_id in ("effective_date", "deadline_alert", "important_deadlines"):
            dates = re.findall(
                r'[০-৯\d]{1,2}[/-][০-৯\d]{1,2}[/-][০-৯\d]{2,4}', context
            )
            if dates:
                return ", ".join(dates)

        return None

    def _llm_extract(self, field, context: str) -> str:
        """Use Gemini to extract/generate field value from context."""
        prompt = f"""You are filling a card field from a Bangla/English document.

FIELD: {field.title}
FIELD TYPE: {field.field_type}

CONTEXT (from the document):
{context}

INSTRUCTIONS:
- Extract or summarize the relevant information for this field
- If the document is in Bangla, respond in Bangla
- If the field type is "ai_summary", write a concise summary
- If the field type is "ai_warning", identify risks or consequences
- If the field type is "list" or "action_list", return a bullet list
- If the field type is "checklist", return items with ✅ or ❌
- If the field type is "table", return as markdown table
- Be concise. Maximum 200 words.
- If information is not available, say "তথ্য পাওয়া যায়নি"

RESPONSE (just the field value, no explanation):"""

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        return response.text.strip()
```

**Test:** Upload a university notice → auto-classify → create card → fill all fields → display in Streamlit with confidence scores.

**Files:** `card_filler.py` (new)  
**Estimated time:** 3-4 hours

---

### Step 11: Confidence Scorer

**Goal:** Score each filled field and the overall card.

**New file:** `scorer.py`

```python
# scorer.py
import re
from dataclasses import dataclass

@dataclass
class ScoreBreakdown:
    source_score: float      # How was the value obtained?
    content_score: float     # Does the value look valid?
    search_score: float      # How good was the search match?
    overall: float

class ConfidenceScorer:
    """Score card fields based on extraction quality."""

    SOURCE_WEIGHTS = {
        "rule_based": 0.95,       # Regex extraction = very reliable
        "ai_extracted": 0.80,     # LLM extraction = good but not perfect
        "user_edited": 1.00,      # User verified = perfect
        "regenerated": 0.85,      # Re-generated = slightly better than first try
        "no_data": 0.05,          # No data found = very low
        "empty": 0.00,
    }

    def score_field(self, field, search_score: float = 0.0) -> float:
        """Score a single field → 0.0 to 1.0"""
        # Component 1: Source reliability
        source_score = self.SOURCE_WEIGHTS.get(field.source, 0.5)

        # Component 2: Content validation
        content_score = self._validate_content(field)

        # Component 3: Search relevance
        search_score = min(search_score, 1.0)

        # Weighted average
        overall = (source_score * 0.4) + (content_score * 0.35) + (search_score * 0.25)
        field.confidence = round(overall, 3)
        return field.confidence

    def _validate_content(self, field) -> float:
        """Check if the field value looks valid."""
        if not field.value or field.value.strip() == "":
            return 0.0

        value = field.value

        # Date fields: check format
        if field.field_type in ("date", "date_list"):
            if re.search(r'[০-৯\d]{1,2}[/-][০-৯\d]{1,2}[/-][০-৯\d]{2,4}', value):
                return 1.0
            return 0.3

        # List/action_list fields: check if it contains multiple items
        if field.field_type in ("list", "action_list", "numbered_steps"):
            lines = [l for l in value.split("\n") if l.strip()]
            if len(lines) >= 2:
                return 0.9
            return 0.5

        # Text/summary fields: check length
        if field.field_type in ("ai_summary", "text", "ai_warning", "ai_suggestion"):
            if len(value) > 50:
                return 0.9
            if len(value) > 20:
                return 0.7
            return 0.4

        # Default
        return 0.7

    def score_card(self, card) -> float:
        """Calculate overall card score from field scores."""
        scores = [f.confidence for f in card.fields]
        if not scores:
            return 0.0
        card.overall_score = round(sum(scores) / len(scores), 3)
        return card.overall_score
```

**Test:** After filling a card, score all fields. Display scores visually in Streamlit.

**Files:** `scorer.py` (new)  
**Estimated time:** 1-2 hours

---

## PHASE 4: Regeneration & Edit System (Steps 12-13)

### Step 12: Regeneration Engine

**Goal:** Allow users to regenerate individual fields, using better context-aware prompts.

**New file:** `regenerator.py`

```python
# regenerator.py
import json
from typing import Optional
from google import genai

class Regenerator:
    """Regenerate card fields with targeted search + LLM."""

    def __init__(self, api_key: str, search_engine, vector_store, embedder):
        self.client = genai.Client(api_key=api_key)
        self.search = search_engine
        self.vector_store = vector_store
        self.embedder = embedder

    def regenerate_field(self, card, field_id: str, document_id: str,
                         user_instruction: str = "") -> dict:
        """
        Regenerate a single field with improved context.
        Returns: {"old_value": ..., "new_value": ..., "confidence": ...}
        """
        field = None
        for f in card.fields:
            if f.field_id == field_id:
                field = f
                break
        if not field:
            raise ValueError(f"Field {field_id} not found in card")

        old_value = field.value

        # Search with more context
        query = f"{field.title} {user_instruction}" if user_instruction else field.title
        results = self.search.hybrid_search(
            query=query,
            vector_store=self.vector_store,
            document_id=document_id,
            top_k=5,  # More chunks for regen
        )

        context = "\n---\n".join([r["content"] for r in results])

        prompt = f"""You are regenerating a card field from a Bangla/English document.

FIELD: {field.title}
FIELD TYPE: {field.field_type}
PREVIOUS VALUE: {old_value}
{"USER INSTRUCTION: " + user_instruction if user_instruction else ""}

DOCUMENT CONTEXT:
{context}

INSTRUCTIONS:
- Generate an IMPROVED value for this field
- Use the document context carefully
- If Bangla content, respond in Bangla
- Be more detailed and accurate than the previous value
- If the user gave instructions, follow them
- Maximum 300 words

NEW VALUE:"""

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        new_value = response.text.strip()

        # Update field
        field.value = new_value
        field.source = "regenerated"
        field.confidence = 0.85

        return {
            "field_id": field_id,
            "old_value": old_value,
            "new_value": new_value,
            "confidence": field.confidence,
        }
```

**Test:** Fill a card → click regenerate on a field → verify new value is better.

**Files:** `regenerator.py` (new)  
**Estimated time:** 2-3 hours

---

### Step 13: Edit Tracking

**Goal:** Track user edits with version history.

**New file:** `edit_tracker.py`

```python
# edit_tracker.py
import json
from datetime import datetime
from typing import List, Dict
from pathlib import Path

class EditTracker:
    """Track field edits and version history."""

    def __init__(self, storage_dir: str = "edit_history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def record_edit(self, card_id: str, field_id: str,
                    old_value: str, new_value: str,
                    source: str = "user_edit") -> dict:
        """Record a field edit."""
        edit = {
            "card_id": card_id,
            "field_id": field_id,
            "old_value": old_value,
            "new_value": new_value,
            "source": source,  # user_edit or regenerated
            "timestamp": datetime.now().isoformat(),
        }

        # Load existing history
        history_file = self.storage_dir / f"{card_id}.json"
        history = self._load_history(history_file)
        history.append(edit)

        # Save
        history_file.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return edit

    def get_history(self, card_id: str, field_id: str = None) -> List[Dict]:
        """Get edit history for a card or specific field."""
        history_file = self.storage_dir / f"{card_id}.json"
        history = self._load_history(history_file)
        if field_id:
            history = [e for e in history if e["field_id"] == field_id]
        return history

    def _load_history(self, path: Path) -> list:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []
```

**Files:** `edit_tracker.py` (new)  
**Estimated time:** 1 hour

---

## PHASE 5: Full Streamlit Integration (Steps 14-16)

### Step 14: Streamlit App — Full Pipeline UI

**Goal:** Rebuild `app.py` to integrate ALL modules into a single sophisticated Streamlit app.

**Rewrite `app.py` with these pages/tabs:**

```
Tab 1: Upload & OCR
  - Upload PDF
  - Run OCR pipeline (existing, enhanced)
  - Show extracted text with image detections
  - Show chunk count and preview

Tab 2: Classification & Card
  - Auto-classify document type
  - Show detected type with confidence
  - Let user override type if wrong
  - Select card template (or auto-selected)
  - Fill card button → runs card_filler
  - Display filled card with confidence badges

Tab 3: Edit & Regenerate
  - Show each card field as editable input
  - Regenerate button per field (if regeneratable=True)
  - Optional user instruction for regeneration
  - Edit tracking (show version count per field)
  - Save changes button

Tab 4: Search & Debug
  - Search box for testing search
  - Toggle: BM25 / Cosine / Hybrid
  - Show search results with scores
  - Show chunk details

Tab 5: Export
  - Download card as JSON
  - Download full pipeline output
  - View edit history
```

**High-level structure for new `app.py`:**

```python
import streamlit as st
# ... imports

st.set_page_config(page_title="Document Intelligence", layout="wide")

# Initialize services (cached)
@st.cache_resource
def init_services():
    embedder = EmbeddingService("paraphrase-multilingual-MiniLM-L12-v2")
    vector_store = VectorStoreChroma()  # or VectorStore() for Pinecone
    search_engine = SearchEngine(embedder)
    classifier = DocumentClassifier(embedder)
    card_manager = CardTemplateManager()
    return embedder, vector_store, search_engine, classifier, card_manager

# Session state for pipeline data
if "doc_result" not in st.session_state:
    st.session_state.doc_result = None
if "chunks" not in st.session_state:
    st.session_state.chunks = None
if "card" not in st.session_state:
    st.session_state.card = None

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📤 Upload & OCR",
    "🏷 Classify & Card",
    "✏️ Edit & Regenerate",
    "🔍 Search Debug",
    "📥 Export",
])

# Each tab implements its functionality...
```

**Files:** `app.py` (rewrite)  
**Estimated time:** 6-8 hours

---

### Step 15: Card Display Component

**Goal:** Beautiful card rendering in Streamlit with confidence badges and edit controls.

```python
# In app.py, Tab 2 — Classify & Card

def render_card(card):
    """Render a filled card in Streamlit."""
    st.subheader(f"📋 {card.template_name}")

    # Overall score badge
    score = card.overall_score
    if score >= 0.8:
        st.success(f"Overall Confidence: {score:.0%} ✅")
    elif score >= 0.6:
        st.warning(f"Overall Confidence: {score:.0%} ⚠️")
    else:
        st.error(f"Overall Confidence: {score:.0%} ❌")

    st.divider()

    for field in card.fields:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{field.title}**")

            # Editable or display-only
            if field.editable:
                new_val = st.text_area(
                    label=field.field_id,
                    value=field.value,
                    key=f"field_{field.field_id}",
                    label_visibility="collapsed",
                )
                if new_val != field.value:
                    # Track edit
                    edit_tracker.record_edit(
                        card.card_id, field.field_id,
                        field.value, new_val, "user_edit"
                    )
                    field.value = new_val
                    field.source = "user_edited"
                    field.confidence = 1.0
            else:
                st.markdown(field.value)

        with col2:
            # Confidence badge
            conf = field.confidence
            if conf >= 0.8:
                st.markdown(f"<span style='color:green'>●</span> {conf:.0%}", unsafe_allow_html=True)
            elif conf >= 0.5:
                st.markdown(f"<span style='color:orange'>●</span> {conf:.0%}", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:red'>●</span> {conf:.0%}", unsafe_allow_html=True)

            # Regenerate button
            if field.regeneratable:
                if st.button("🔄", key=f"regen_{field.field_id}"):
                    st.session_state[f"regen_target"] = field.field_id

        st.divider()
```

**Files:** Part of `app.py`  
**Estimated time:** 3-4 hours

---

### Step 16: Search Debug Panel

**Goal:** Interactive search testing in Streamlit.

```python
# In app.py, Tab 4 — Search Debug

with tab4:
    st.subheader("🔍 Search Engine Tester")
    query = st.text_input("Search query (Bangla or English)")
    method = st.radio("Method", ["Hybrid", "BM25 Only", "Cosine Only"], horizontal=True)

    if query and st.session_state.chunks:
        if method == "BM25 Only":
            results = search_engine.bm25_search(query, top_k=5)
        elif method == "Cosine Only":
            results = search_engine.cosine_search(
                query, vector_store, st.session_state.document_id, top_k=5
            )
        else:
            results = search_engine.hybrid_search(
                query, vector_store, st.session_state.document_id, top_k=5
            )

        for i, r in enumerate(results):
            with st.expander(f"Result {i+1} — Score: {r['score']:.3f} | {r.get('search_method', '')}"):
                st.write(f"**Chunk Type:** {r['chunk_type']}")
                st.write(f"**Page:** {r['page_number']}")
                st.write(r["content"])
```

**Files:** Part of `app.py`  
**Estimated time:** 1-2 hours

---

## COMPLETE FILE STRUCTURE AFTER ALL STEPS

```
OCR/
├── app.py                    # Streamlit UI (rewritten in Step 14)
├── pdf.py                    # PDF → Image converter (existing, unchanged)
├── ocr_engine.py             # Step 2-3: Gemini OCR with structured output
├── chunker.py                # Step 4: Semantic text chunking
├── embedder.py               # Step 5: Free local embeddings
├── vector_store.py           # Step 6: Pinecone vector DB
├── vector_store_chroma.py    # Step 6B: ChromaDB alternative
├── search_engine.py          # Step 7: BM25 + Cosine + Hybrid search
├── classifier.py             # Step 8: Document type classifier
├── card_manager.py           # Step 9: Card template manager
├── card_filler.py            # Step 10: LLM-powered card filling
├── scorer.py                 # Step 11: Confidence scoring
├── regenerator.py            # Step 12: Field regeneration
├── edit_tracker.py           # Step 13: Edit version tracking
├── pdftypes.txt              # PDF type definitions (existing)
├── templateStructure.txt     # Card templates (existing)
├── .env                      # API keys
├── requirements.txt          # Dependencies
├── chroma_db/                # ChromaDB persistent storage (auto-created)
├── edit_history/             # Edit tracking JSONs (auto-created)
├── output_images/            # Page images (existing)
├── output_jsons/             # Per-page OCR JSONs (existing)
├── merged_outputs/           # Merged JSONs (existing)
└── plan/                     # Planning docs (existing)
```

---

## DEPENDENCIES (requirements.txt)

```
# Core
google-genai
python-dotenv
Pillow
pdf2image

# Embedding (FREE, local)
sentence-transformers
torch

# Vector Database (pick one)
pinecone           # Option A: Pinecone (free tier, cloud)
chromadb            # Option B: ChromaDB (fully local)

# Search
rank-bm25
numpy

# UI
streamlit
```

---

## EXECUTION ORDER & TIMELINE

| Step | What                                       | Depends On   | Time | Phase          |
| ---- | ------------------------------------------ | ------------ | ---- | -------------- |
| 1    | Improve OCR prompt (images, mixed content) | Nothing      | 1-2h | OCR            |
| 2    | OCR Engine module (`ocr_engine.py`)        | Step 1       | 2-3h | OCR            |
| 3    | Multi-page document assembly               | Step 2       | 1-2h | OCR            |
| 4    | Text chunker (`chunker.py`)                | Step 3       | 2-3h | Chunking       |
| 5    | Embedding service (`embedder.py`)          | Step 4       | 1-2h | Embedding      |
| 6    | Vector store (Pinecone or ChromaDB)        | Step 5       | 2-3h | Vector DB      |
| 7    | BM25 + Hybrid search (`search_engine.py`)  | Step 5, 6    | 3-4h | Search         |
| 8    | Document classifier (`classifier.py`)      | Step 5       | 1-2h | Classification |
| 9    | Card template manager (`card_manager.py`)  | Nothing      | 1-2h | Cards          |
| 10   | Card filler with LLM (`card_filler.py`)    | Step 7, 8, 9 | 3-4h | Cards          |
| 11   | Confidence scorer (`scorer.py`)            | Step 10      | 1-2h | Scoring        |
| 12   | Regeneration engine (`regenerator.py`)     | Step 7, 10   | 2-3h | Regen          |
| 13   | Edit tracker (`edit_tracker.py`)           | Nothing      | 1h   | Tracking       |
| 14   | Streamlit full integration (`app.py`)      | All above    | 6-8h | UI             |
| 15   | Card display component                     | Step 14      | 3-4h | UI             |
| 16   | Search debug panel                         | Step 14      | 1-2h | UI             |

**Total estimated: ~32-48 hours of focused work**

---

## PIPELINE FLOW (After All Steps)

```
PDF Upload
    │
    ▼
[pdf.py] PDF → Images (300 DPI)
    │
    ▼
[ocr_engine.py] Gemini 2.5 Flash OCR
    │   ├── Extract Bangla text (as-is, no translation)
    │   ├── Extract English text
    │   ├── Identify images/logos/signatures/seals
    │   └── Structured JSON per page
    │
    ▼
[ocr_engine.py] DocumentOCRResult (merged all pages)
    │
    ▼
[chunker.py] Semantic Chunking
    │   ├── Respect section boundaries (header/para/table/list)
    │   ├── Max 512 tokens, 64 overlap
    │   ├── Image descriptions as separate chunks
    │   └── Bangla-aware token counting
    │
    ▼
[embedder.py] Generate Embeddings (FREE - local model)
    │   └── paraphrase-multilingual-MiniLM-L12-v2
    │
    ▼
[vector_store.py] Store in Pinecone/ChromaDB
    │
    ▼
[search_engine.py] Build BM25 Index
    │
    ▼
[classifier.py] Classify Document Type
    │   └── → PDF001/PDF002/PDF003/PDF004/PDF005
    │
    ▼
[card_manager.py] Create Card from Template
    │
    ▼
[card_filler.py] Fill Card Fields
    │   ├── Hybrid Search (BM25 + Cosine) per field
    │   ├── Rule-based extraction (dates, numbers → FREE)
    │   └── LLM post-processing (summaries, analysis → Gemini)
    │
    ▼
[scorer.py] Confidence Scoring per field
    │
    ▼
[app.py] Display Card in Streamlit
    │
    ▼
[regenerator.py] User clicks Regenerate
    │   ├── More context chunks (top-5 instead of top-3)
    │   ├── Previous value as reference
    │   └── Optional user instruction
    │
    ▼
[edit_tracker.py] Track all edits + regenerations
    │
    ▼
[app.py] Export JSON / Download
```

---

## START HERE → FIRST COMMAND TO RUN

```bash
# Install all new dependencies
pip install sentence-transformers rank-bm25 chromadb pinecone numpy
```

Then start with **Step 1** — just change the OCR prompt in `app.py` and test with a Bangla PDF that has images.
