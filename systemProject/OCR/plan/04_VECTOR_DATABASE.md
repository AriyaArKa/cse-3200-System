# 04 — Vector Database Strategy

## Vector DB Comparison (Your Context)

| Feature                 | FAISS                   | ChromaDB                  | Pinecone               | Weaviate                     |
| ----------------------- | ----------------------- | ------------------------- | ---------------------- | ---------------------------- |
| **Cost**                | Free (local)            | Free (local)              | $70+/mo                | Free (local) / $25+/mo cloud |
| **Setup**               | `pip install faiss-cpu` | `pip install chromadb`    | API key only           | Docker required              |
| **Metadata filtering**  | Manual                  | Built-in                  | Built-in               | Built-in (GraphQL)           |
| **Persistence**         | File-based              | SQLite-backed             | Cloud-managed          | File/Docker                  |
| **Max vectors (local)** | 10M+ (RAM)              | 1M+                       | Unlimited (cloud)      | 10M+                         |
| **Update vectors**      | Replace by ID           | Upsert                    | Upsert                 | Upsert                       |
| **Query speed**         | Fastest                 | Fast                      | Fast (network latency) | Fast                         |
| **Python API**          | Low-level               | High-level                | High-level             | High-level                   |
| **Best for**            | Performance             | **Simplicity + Features** | Managed scale          | Enterprise                   |

### Recommendation

| Phase                  | Choice                       | Why                                                                  |
| ---------------------- | ---------------------------- | -------------------------------------------------------------------- |
| **MVP**                | **ChromaDB**                 | Zero cost, built-in metadata filtering, easy API, persistent storage |
| **Scale (100K+ docs)** | ChromaDB (still) or Pinecone | ChromaDB handles millions; Pinecone if you want managed              |
| **Enterprise**         | Pinecone or Weaviate Cloud   | SLA, managed infrastructure                                          |

---

## ChromaDB Implementation

```python
# vector_repo.py
import chromadb
from chromadb.config import Settings

class VectorRepository:
    """ChromaDB-based vector storage with metadata filtering."""

    def __init__(self, persist_dir: str = "./vector_db"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # One collection per document type for efficient querying
        self.collections = {
            "documents": self.client.get_or_create_collection(
                name="document_chunks",
                metadata={"hnsw:space": "cosine"}  # Cosine similarity
            )
        }

    def store_chunks(self, chunks: list[dict]):
        """Store chunks with embeddings and metadata."""
        self.collections["documents"].upsert(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=[c["embedding"] for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[{
                "document_id": c["document_id"],
                "page_number": c["page_number"],
                "chunk_type": c["chunk_type"],
                "token_count": c["token_count"],
                "ocr_confidence": c.get("ocr_confidence", 0.0),
                "has_bangla": c["metadata"]["has_bangla"],
                "has_table": c["metadata"]["has_table"],
                "level": c.get("level", 2),
            } for c in chunks]
        )

    def query_for_field(
        self,
        query_embedding: list[float],
        document_id: str,
        field_type: str = None,
        top_k: int = 5
    ) -> list[dict]:
        """Query chunks relevant to a specific card field."""

        # Build metadata filter
        where_filter = {"document_id": document_id}

        if field_type == "date":
            where_filter["has_dates"] = True  # Only search date-containing chunks
        elif field_type == "table":
            where_filter["has_table"] = True

        results = self.collections["documents"].query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        return [{
            "chunk_id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": 1 - results["distances"][0][i],  # Convert distance to similarity
        } for i in range(len(results["ids"][0]))]

    def update_chunk(self, chunk_id: str, new_content: str, new_embedding: list[float]):
        """Update a chunk after user edit (re-embed)."""
        self.collections["documents"].update(
            ids=[chunk_id],
            embeddings=[new_embedding],
            documents=[new_content]
        )

    def delete_document_chunks(self, document_id: str):
        """Remove all chunks for a document (on re-upload or delete)."""
        self.collections["documents"].delete(
            where={"document_id": document_id}
        )
```

---

## Embedding Model Selection

| Model                           | Dimensions | Size   | Quality (MTEB) | Cost                 | Speed      |
| ------------------------------- | ---------- | ------ | -------------- | -------------------- | ---------- |
| **all-MiniLM-L6-v2**            | 384        | 80 MB  | 0.63           | **Free (local)**     | **Fast**   |
| all-mpnet-base-v2               | 768        | 420 MB | 0.65           | Free (local)         | Medium     |
| text-embedding-3-small (OpenAI) | 1536       | API    | 0.62           | $0.02/1M tokens      | Slow (API) |
| Gemini text-embedding           | 768        | API    | 0.64           | $0.00/1M (free tier) | Slow (API) |
| multilingual-e5-small           | 384        | 470 MB | 0.61           | Free (local)         | Medium     |

### Recommendation: **all-MiniLM-L6-v2** for MVP

**Why:**

- Runs locally = **zero API cost** forever
- 384 dimensions = small storage footprint
- Good enough quality for document retrieval
- Fast: ~3000 chunks/second on CPU

**For Bangla-heavy content (Phase 2):** Consider `multilingual-e5-small` — better multilingual support, same dimension, slightly slower.

```python
# Switch models without changing code:
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # MVP
# EMBEDDING_MODEL = "intfloat/multilingual-e5-small"  # Phase 2

model = SentenceTransformer(EMBEDDING_MODEL)
```

---

## Index Type Strategy

ChromaDB uses HNSW (Hierarchical Navigable Small World) internally. Configuration:

```python
collection = client.get_or_create_collection(
    name="document_chunks",
    metadata={
        "hnsw:space": "cosine",        # Distance metric
        "hnsw:construction_ef": 128,    # Build quality (higher = better, slower build)
        "hnsw:search_ef": 64,           # Search quality (higher = better, slower query)
        "hnsw:M": 16,                   # Connections per node (16 is optimal default)
    }
)
```

| Param           | Low Value                 | High Value                 | Recommendation              |
| --------------- | ------------------------- | -------------------------- | --------------------------- |
| construction_ef | Fast build, lower recall  | Slow build, better recall  | 128 (good balance)          |
| search_ef       | Fast query, lower recall  | Slow query, better recall  | 64 for <100K, 128 for >100K |
| M               | Less memory, lower recall | More memory, better recall | 16 (default, optimal)       |

---

## Metadata Filtering Patterns

```python
# Pattern 1: Get chunks for a specific document
results = collection.query(
    query_embeddings=[embed],
    where={"document_id": "doc_123"}
)

# Pattern 2: Get only table chunks from financial documents
results = collection.query(
    query_embeddings=[embed],
    where={
        "$and": [
            {"document_id": "doc_123"},
            {"chunk_type": "table"},
            {"has_bangla": True}
        ]
    }
)

# Pattern 3: Get high-confidence chunks only
results = collection.query(
    query_embeddings=[embed],
    where={
        "$and": [
            {"document_id": "doc_123"},
            {"ocr_confidence": {"$gte": 0.8}}
        ]
    }
)

# Pattern 4: Get page-level chunks for context
results = collection.query(
    query_embeddings=[embed],
    where={
        "$and": [
            {"document_id": "doc_123"},
            {"level": 1},  # Page-level chunks
            {"page_number": {"$in": [1, 2, 3]}}
        ]
    }
)
```

---

## Updating Embeddings After User Edits

```python
class VectorUpdateService:
    """Handle vector DB updates when users edit card fields."""

    def __init__(self, vector_repo, embedding_service):
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service

    def on_user_edit(self, chunk_id: str, old_content: str, new_content: str):
        """Called when user edits a card field that maps to a chunk."""

        # Only re-embed if content changed significantly
        if self._significant_change(old_content, new_content):
            new_embedding = self.embedding_service.embed_query(new_content)
            self.vector_repo.update_chunk(chunk_id, new_content, new_embedding)

    def on_regeneration(self, document_id: str, field_id: str, new_content: str):
        """Called when AI regenerates a field — update the relevant chunk."""
        # Find which chunk(s) this field maps to
        query_embed = self.embedding_service.embed_query(new_content)

        # Get closest existing chunk
        matches = self.vector_repo.query_for_field(
            query_embed, document_id, top_k=1
        )

        if matches:
            self.vector_repo.update_chunk(
                matches[0]["chunk_id"],
                new_content,
                query_embed
            )

    def _significant_change(self, old: str, new: str, threshold: float = 0.3) -> bool:
        """Skip re-embedding for trivial edits (typo fixes)."""
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, old, new).ratio()
        return ratio < (1 - threshold)  # True if >30% changed
```

---

## Storage Architecture

```
vector_db/                          # ChromaDB persistent storage
├── chroma.sqlite3                  # Metadata + chunk text (SQLite)
├── index/                          # HNSW index files
│   ├── uuid-uuid-uuid/
│   │   ├── header.bin
│   │   ├── data_level0.bin         # Vector data
│   │   └── length.bin
│   └── ...
└── ...

# Size estimates:
# 10,000 chunks (384-dim): ~20 MB total
# 100,000 chunks:          ~200 MB total
# 1,000,000 chunks:        ~2 GB total → still fits on a single server
```
