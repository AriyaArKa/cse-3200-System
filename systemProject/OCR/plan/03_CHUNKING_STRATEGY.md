# 03 — Chunking Strategy

## Why Chunking Matters

Your OCR outputs full-page JSON. But for:

- **RAG retrieval** → you need smaller, semantically meaningful chunks
- **Field extraction** → you need chunks aligned to document sections
- **Regeneration** → you need to re-query only the relevant context, not the whole document

---

## Chunking Approaches Compared

| Approach                         | Pros                   | Cons                      | Best For                    |
| -------------------------------- | ---------------------- | ------------------------- | --------------------------- |
| **Fixed-size (token count)**     | Simple, predictable    | Breaks mid-sentence/table | Generic search              |
| **Sentence-based**               | Preserves meaning      | Too small for context     | Simple docs                 |
| **Semantic (paragraph/section)** | Best retrieval quality | Needs section detection   | **Your use case**           |
| **Hierarchical**                 | Multi-resolution       | Complex to implement      | **Your use case (Phase 2)** |

### Recommendation: **Semantic chunking (MVP) → Hierarchical (Phase 2)**

---

## Semantic Chunking Implementation

### Core Algorithm

```python
import re
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    page_number: int
    content: str
    chunk_type: str           # "header", "paragraph", "table", "list", "metadata"
    token_count: int
    start_position: int       # Character offset in original text
    end_position: int
    metadata: dict = field(default_factory=dict)

    # Populated after embedding
    embedding: Optional[list] = None


class SemanticChunker:
    """Chunk OCR output by semantic boundaries."""

    MAX_CHUNK_TOKENS = 512     # Sweet spot for embedding models
    MIN_CHUNK_TOKENS = 50      # Avoid tiny fragments
    OVERLAP_TOKENS = 64        # Context window overlap

    def chunk_document(self, ocr_pages: list[dict], document_id: str) -> list[Chunk]:
        """Chunk all pages of a document."""
        all_chunks = []

        for page_num, page_data in enumerate(ocr_pages):
            page_text = self._extract_text_from_ocr(page_data)
            sections = self._detect_sections(page_text)

            for section in sections:
                # If section is small enough, it's one chunk
                if self._count_tokens(section["text"]) <= self.MAX_CHUNK_TOKENS:
                    all_chunks.append(self._make_chunk(
                        section, document_id, page_num
                    ))
                else:
                    # Split large sections with overlap
                    sub_chunks = self._split_with_overlap(
                        section, document_id, page_num
                    )
                    all_chunks.extend(sub_chunks)

        return all_chunks

    def _detect_sections(self, text: str) -> list[dict]:
        """Split text into semantic sections based on structure."""
        sections = []
        current_section = {"type": "paragraph", "text": "", "start": 0}

        lines = text.split("\n")
        pos = 0

        for line in lines:
            stripped = line.strip()

            # Detect section type
            if self._is_header(stripped):
                # Save current section
                if current_section["text"].strip():
                    sections.append(current_section.copy())
                current_section = {
                    "type": "header",
                    "text": stripped + "\n",
                    "start": pos
                }
            elif self._is_table_row(stripped):
                if current_section["type"] != "table":
                    if current_section["text"].strip():
                        sections.append(current_section.copy())
                    current_section = {
                        "type": "table",
                        "text": stripped + "\n",
                        "start": pos
                    }
                else:
                    current_section["text"] += stripped + "\n"
            elif self._is_list_item(stripped):
                if current_section["type"] != "list":
                    if current_section["text"].strip():
                        sections.append(current_section.copy())
                    current_section = {
                        "type": "list",
                        "text": stripped + "\n",
                        "start": pos
                    }
                else:
                    current_section["text"] += stripped + "\n"
            elif stripped == "":
                # Paragraph break
                if current_section["text"].strip():
                    sections.append(current_section.copy())
                    current_section = {
                        "type": "paragraph",
                        "text": "",
                        "start": pos
                    }
            else:
                current_section["text"] += stripped + " "

            pos += len(line) + 1

        # Don't forget last section
        if current_section["text"].strip():
            sections.append(current_section)

        return sections

    def _is_header(self, line: str) -> bool:
        """Heuristic: short lines, all caps, or common header patterns."""
        if not line:
            return False
        # Bengali/English header patterns
        if len(line) < 100 and (
            line.isupper() or
            line.endswith(":") or
            re.match(r'^[\d]+[\.\)]\s', line) or  # "1. Section"
            re.match(r'^(বিষয়|তারিখ|স্মারক|প্রতি|সূত্র)', line)  # Bengali headers
        ):
            return True
        return False

    def _is_table_row(self, line: str) -> bool:
        """Detect table rows by pipe or tab separators."""
        return "|" in line or line.count("\t") >= 2

    def _is_list_item(self, line: str) -> bool:
        """Detect list items."""
        return bool(re.match(r'^[\-\•\*\d]+[\.\)]\s', line))

    def _split_with_overlap(self, section: dict, doc_id: str, page: int) -> list[Chunk]:
        """Split large section into overlapping chunks."""
        words = section["text"].split()
        chunks = []

        # Approximate: 1 token ≈ 0.75 words for English, ~0.5 for Bangla
        words_per_chunk = int(self.MAX_CHUNK_TOKENS * 0.6)  # Conservative for Bangla
        overlap_words = int(self.OVERLAP_TOKENS * 0.6)

        start = 0
        while start < len(words):
            end = min(start + words_per_chunk, len(words))
            chunk_text = " ".join(words[start:end])

            chunks.append(self._make_chunk(
                {"type": section["type"], "text": chunk_text, "start": section["start"]},
                doc_id, page
            ))

            start = end - overlap_words  # Overlap
            if start >= len(words) - overlap_words:
                break

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Approximate token count. Use tiktoken for accuracy."""
        # Bangla characters ≈ 1.5-2 tokens each in most models
        bangla_chars = len(re.findall(r'[\u0980-\u09FF]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return bangla_chars * 2 + english_words

    def _make_chunk(self, section: dict, doc_id: str, page: int) -> Chunk:
        import uuid
        return Chunk(
            chunk_id=uuid.uuid4().hex[:12],
            document_id=doc_id,
            page_number=page,
            content=section["text"],
            chunk_type=section["type"],
            token_count=self._count_tokens(section["text"]),
            start_position=section["start"],
            end_position=section["start"] + len(section["text"]),
            metadata={
                "has_bangla": bool(re.search(r'[\u0980-\u09FF]', section["text"])),
                "has_table": section["type"] == "table",
                "has_dates": bool(re.search(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', section["text"])),
            }
        )
```

---

## Overlap Strategy

```
┌──────────────────────────────────┐
│          CHUNK 1                 │
│  ........text content.........  │
│  .............................  │
│  ...........┌────────────────│──────────────────────┐
│             │   OVERLAP      │                      │
└─────────────│────────────────┘    CHUNK 2           │
              │   64 tokens    │                      │
              │  (shared ctx)  │  ........text.......  │
              └────────────────│──────────────────────┘
```

**Why 64 tokens overlap:**

- Enough to preserve sentence boundaries
- Prevents information loss at chunk boundaries
- Embedding models handle this well
- ~12% storage overhead (acceptable)

---

## Hierarchical Chunking (Phase 2)

Three levels of chunks for multi-resolution retrieval:

```
Level 0 (Document): Full document summary (1 chunk per doc)
    │
    ├── Level 1 (Page): Page-level content (1 chunk per page)
    │       │
    │       ├── Level 2 (Section): Individual sections/paragraphs
    │       │       │
    │       │       └── "বিষয়: ছুটি ঘোষণা..."
    │       │       └── "তারিখ: ১২/০৩/২০২৬"
    │       │       └── [Table data]
    │       │
    │       └── Level 2 (Section): ...
    │
    └── Level 1 (Page): ...
```

```python
@dataclass
class HierarchicalChunk:
    """Multi-level chunk with parent-child relationships."""
    chunk_id: str
    parent_chunk_id: Optional[str]  # None for Level 0
    level: int                       # 0=doc, 1=page, 2=section
    content: str
    summary: Optional[str]           # AI-generated summary for L0 and L1
    children: list[str]              # child chunk_ids

# Retrieval strategy:
# 1. Search at Level 2 (finest granularity)
# 2. If match found, also fetch parent (Level 1) for context
# 3. Rank by combined score
```

---

## Metadata Structure Per Chunk

```json
{
  "chunk_id": "a1b2c3d4e5f6",
  "document_id": "doc_uuid_here",
  "page_number": 1,
  "chunk_index": 3,
  "level": 2,

  "content": "বিষয়: ছুটি ঘোষণা ও শিক্ষা কার্যক্রম বন্ধ থাকা প্রসঙ্গে।...",
  "chunk_type": "paragraph",

  "token_count": 245,
  "start_position": 1024,
  "end_position": 1456,

  "parent_chunk_id": "page_chunk_001",
  "sibling_chunk_ids": ["a1b2c3d4e5f5", "a1b2c3d4e5f7"],

  "metadata": {
    "language": "bn",
    "has_bangla": true,
    "has_table": false,
    "has_dates": true,
    "detected_dates": ["12/03/2026"],
    "detected_entities": ["বিভাগীয় প্রধান", "ডিন অফিস"],
    "ocr_method": "native",
    "ocr_confidence": 0.95
  },

  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": null
}
```

---

## Handling Multi-Page Context

Some information spans multiple pages (e.g., a table starting on page 2 and ending on page 3).

```python
class CrossPageChunker:
    """Handle content that spans page boundaries."""

    def merge_cross_page_content(self, pages: list[dict]) -> list[dict]:
        """Detect and merge content spanning page boundaries."""
        merged_pages = []

        i = 0
        while i < len(pages):
            page = pages[i].copy()

            # Check if last element of this page continues on next page
            if i + 1 < len(pages):
                last_line = page["text"].rstrip().split("\n")[-1]
                first_line = pages[i + 1]["text"].lstrip().split("\n")[0]

                if self._is_continuation(last_line, first_line):
                    # Merge: append next page's first paragraph to this page
                    continuation = self._extract_first_paragraph(pages[i + 1]["text"])
                    page["text"] += "\n" + continuation
                    page["metadata"]["spans_pages"] = [i, i + 1]

            merged_pages.append(page)
            i += 1

        return merged_pages

    def _is_continuation(self, last_line: str, first_line: str) -> bool:
        """Heuristic: does content flow across page break?"""
        # Unfinished sentence (no period at end)
        if last_line and not last_line[-1] in ".।:;!?":
            return True
        # Table continuation (row-like structure)
        if self._is_table_row(last_line) and self._is_table_row(first_line):
            return True
        return False
```

---

## Embedding Storage Strategy

```python
# embedding_service.py
from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingService:
    """Generate and store embeddings for chunks."""

    def __init__(self):
        # all-MiniLM-L6-v2: 384-dim, 80MB model, runs on CPU
        # Good quality for semantic search, FREE (local)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def embed_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Batch embed all chunks (efficient)."""
        texts = [c.content for c in chunks]

        # Batch encoding is 10x faster than one-by-one
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True  # For cosine similarity
        )

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding.tolist()

        return chunks

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a search query."""
        return self.model.encode(query, normalize_embeddings=True)
```

### Storage Cost Estimate

| Component                   | Size per chunk | 10K chunks | 100K chunks |
| --------------------------- | -------------- | ---------- | ----------- |
| Embedding (384-dim float32) | 1.5 KB         | 15 MB      | 150 MB      |
| Metadata JSON               | ~0.5 KB        | 5 MB       | 50 MB       |
| Content text                | ~2 KB          | 20 MB      | 200 MB      |
| **Total**                   | ~4 KB          | **40 MB**  | **400 MB**  |

All fits in RAM for FAISS. No cloud costs needed until 1M+ chunks.
