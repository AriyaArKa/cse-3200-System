# 06 — Cost Optimization Strategy

## Cost Breakdown (Current vs Optimized)

### Current Cost Model (No Optimization)

| Operation               | Cost Per Unit | 1000 Docs/Day (avg 5 pages) | Monthly       |
| ----------------------- | ------------- | --------------------------- | ------------- |
| Gemini OCR (every page) | ~$0.015/page  | $75/day                     | **$2,250**    |
| Card generation (LLM)   | ~$0.005/card  | $5/day                      | $150          |
| Regeneration calls      | ~$0.005/call  | $10/day                     | $300          |
| Total                   |               |                             | **$2,700/mo** |

### Optimized Cost Model

| Operation       | Strategy                        | Cost            | Monthly     |
| --------------- | ------------------------------- | --------------- | ----------- |
| OCR             | Hybrid (native first)           | $0.005/page avg | **$750**    |
| Card generation | Cached prompts + JSON schema    | $0.003/card     | $90         |
| Regeneration    | Isolated context (small prompt) | $0.002/call     | $60         |
| Embeddings      | Local model (free)              | $0              | **$0**      |
| Vector DB       | ChromaDB local (free)           | $0              | **$0**      |
| Total           |                                 |                 | **$900/mo** |

**Savings: ~67% ($1,800/month)**

---

## Strategy 1: Model Routing (Small vs Large LLM)

```
┌────────────────────────────┐
│ Incoming Task               │
└──────────┬─────────────────┘
           │
     ┌─────▼──────┐
     │ Task Type? │
     └─────┬──────┘
           │
    ┌──────┼──────────────────┐
    │      │                  │
    ▼      ▼                  ▼
┌────────┐ ┌────────────┐ ┌──────────────┐
│ Simple │ │ Medium     │ │ Complex      │
│        │ │            │ │              │
│ Regex  │ │ Gemini     │ │ Gemini 2.5   │
│ Rules  │ │ 2.0 Flash  │ │ Flash (full) │
│ FREE   │ │ $0.001     │ │ $0.01+       │
│        │ │            │ │              │
│ Dates  │ │ Summary    │ │ Bangla OCR   │
│ Numbers│ │ Simple Q&A │ │ Complex      │
│ Emails │ │ Basic fill │ │ analysis     │
│ Phones │ │            │ │ Cross-ref    │
└────────┘ └────────────┘ └──────────────┘
```

### Implementation

```python
class ModelRouter:
    """Route tasks to cheapest capable model."""

    def select_model(self, task_type: str, complexity: str) -> dict:
        """Select optimal model for the task."""

        routing_table = {
            # (task_type, complexity) → model config
            ("extract_date", "any"):       {"model": "regex", "cost": 0},
            ("extract_number", "any"):     {"model": "regex", "cost": 0},
            ("extract_email", "any"):      {"model": "regex", "cost": 0},
            ("extract_phone", "any"):      {"model": "regex", "cost": 0},

            ("summarize", "simple"):       {"model": "gemini-2.0-flash", "cost": 0.001},
            ("fill_field", "simple"):      {"model": "gemini-2.0-flash", "cost": 0.001},
            ("classify_type", "any"):      {"model": "gemini-2.0-flash", "cost": 0.001},

            ("ocr", "scanned"):           {"model": "gemini-2.5-flash", "cost": 0.015},
            ("summarize", "complex"):      {"model": "gemini-2.5-flash", "cost": 0.005},
            ("regenerate", "complex"):     {"model": "gemini-2.5-flash", "cost": 0.005},
            ("analyze", "any"):           {"model": "gemini-2.5-flash", "cost": 0.008},
        }

        key = (task_type, complexity)
        if key in routing_table:
            return routing_table[key]

        # Fallback: check simpler key
        key = (task_type, "any")
        return routing_table.get(key, {"model": "gemini-2.5-flash", "cost": 0.01})
```

---

## Strategy 2: When to Avoid LLM Completely

```python
class RuleBasedExtractor:
    """Extract values without LLM — zero cost."""

    PATTERNS = {
        "date_bangla": r'[\u09E6-\u09EF]{1,2}[/\-\.][\u09E6-\u09EF]{1,2}[/\-\.][\u09E6-\u09EF]{2,4}',
        "date_english": r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}',
        "iso_date": r'\d{4}-\d{2}-\d{2}',
        "email": r'[\w\.-]+@[\w\.-]+\.\w+',
        "phone": r'(?:\+?880|0)\d{10}',
        "money_bdt": r'(?:৳|BDT|Tk\.?)\s*[\d,]+(?:\.\d{2})?',
        "memo_number": r'(?:স্মারক|Memo|Ref)\s*(?:নং|No\.?)[:\s]*[\w\-/]+',
        "percentage": r'\d+(?:\.\d+)?%',
        "url": r'https?://[\w\-\.]+(?:/[\w\-\./?%&=]*)?',
    }

    def extract_all(self, text: str) -> dict:
        """Extract all rule-based fields. Cost: $0."""
        results = {}
        for field_name, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                results[field_name] = matches
        return results

    def can_handle(self, field_type: str) -> bool:
        """Check if this field can be extracted without LLM."""
        no_llm_types = {"date", "email", "phone", "number", "url", "memo_number"}
        return field_type in no_llm_types
```

---

## Strategy 3: Multi-Layer Caching

```
Request comes in
    │
    ▼
┌─────────────────────┐
│ L1: In-Memory Cache  │  ← Hot data, <1ms access
│ (LRU, 1000 entries) │  ← Recent OCR results, embeddings
│ Python dict / lru_cache │
└─────────┬───────────┘
          │ MISS
          ▼
┌─────────────────────┐
│ L2: Redis Cache     │  ← Warm data, ~1ms access
│ (TTL: 30 days)      │  ← OCR results keyed by page hash
│                     │  ← Card templates, scored outputs
└─────────┬───────────┘
          │ MISS
          ▼
┌─────────────────────┐
│ L3: PostgreSQL      │  ← Cold data, ~5ms access
│ (Permanent)         │  ← All historical data
└─────────┬───────────┘
          │ MISS
          ▼
┌─────────────────────┐
│ L4: Gemini API Call  │  ← Expensive! Only when necessary
│ ($$$)               │
└─────────────────────┘
```

### Implementation

```python
import functools
import hashlib
import json
from redis import Redis

class CacheManager:
    """Multi-layer caching to minimize API calls."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self._memory_cache = {}

    @functools.lru_cache(maxsize=500)
    def get_ocr_result_memory(self, page_hash: str):
        """L1: In-memory cache."""
        return None  # LRU cache handles this

    def get_ocr_result(self, page_hash: str) -> dict | None:
        """Check all cache layers."""

        # L1: Memory
        if page_hash in self._memory_cache:
            return self._memory_cache[page_hash]

        # L2: Redis
        cached = self.redis.get(f"ocr:{page_hash}")
        if cached:
            result = json.loads(cached)
            self._memory_cache[page_hash] = result  # Promote to L1
            return result

        return None  # Cache miss → need API call

    def set_ocr_result(self, page_hash: str, result: dict, ttl_days: int = 30):
        """Store in all cache layers."""
        self._memory_cache[page_hash] = result
        self.redis.setex(
            f"ocr:{page_hash}",
            ttl_days * 86400,
            json.dumps(result, ensure_ascii=False)
        )

    def get_card_template_result(self, document_hash: str, template_id: str):
        """Cache filled card templates."""
        key = f"card:{document_hash}:{template_id}"
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None

    def invalidate_document(self, document_id: str):
        """Clear all caches for a document (on re-upload)."""
        pattern = f"*:{document_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
```

---

## Strategy 4: Token Reduction Techniques

### 4a. Prompt Compression

```python
# BEFORE (expensive): 90 tokens prompt + full page context = ~2000 tokens
prompt = f"""
You are an AI assistant that extracts structured information from documents.
Given the following OCR text from a university notice, please extract
the notice title, department name, issue date, and any important deadlines.
Format your response as JSON with the following fields...

OCR Text:
{full_page_text}  # Could be 1500+ tokens
"""

# AFTER (cheap): 30 tokens prompt + relevant chunks only = ~400 tokens
prompt = f"""Extract fields as JSON: title, department, date, deadlines.

Context:
{relevant_chunks_only}  # Only 200-300 tokens (from vector search)
"""
```

**Savings:** 80% token reduction per request

### 4b. JSON Schema Enforcement

```python
# Forces model to output exact structure — no wasted tokens on formatting
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[prompt, image],
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": target_schema,
        "max_output_tokens": 500,  # Cap output length
        "temperature": 0.1,        # Deterministic = fewer retries
    }
)
```

### 4c. Context Window Optimization

```python
def build_minimal_context(self, document_id: str, field_id: str) -> str:
    """Build smallest possible context for field extraction."""

    # Instead of sending full document, query vector DB for relevant chunks
    query = self._field_to_query(field_id)
    # e.g., "issue_date" → "date তারিখ issued when"

    relevant_chunks = self.vector_repo.query_for_field(
        query_embedding=self.embed(query),
        document_id=document_id,
        top_k=3,  # Only 3 most relevant chunks
    )

    # Concatenate only relevant context
    context = "\n---\n".join(c["content"] for c in relevant_chunks)
    return context[:1000]  # Hard cap at ~250 tokens
```

---

## Strategy 5: Smart Retry Without Cost Increase

```python
class SmartRetry:
    """Retry failed extractions without wasting money."""

    async def extract_with_retry(self, task, max_retries=2):
        for attempt in range(max_retries + 1):
            try:
                result = await self._attempt_extraction(task, attempt)
                if result and self._is_valid(result):
                    return result
            except Exception as e:
                if attempt == max_retries:
                    return self._fallback(task)

        return self._fallback(task)

    async def _attempt_extraction(self, task, attempt: int):
        """Each retry uses a different strategy (not just repeating)."""

        if attempt == 0:
            # First try: cheapest model
            return await self._try_regex(task)

        elif attempt == 1:
            # Second try: small LLM with focused prompt
            return await self._try_small_llm(task)

        elif attempt == 2:
            # Last try: full model with expanded context
            return await self._try_full_llm(task)

    def _fallback(self, task) -> dict:
        """Return partial result with low confidence instead of failing."""
        return {
            "value": None,
            "confidence": 0.0,
            "status": "extraction_failed",
            "needs_manual_input": True,
        }
```

---

## Strategy 6: Embedding Cost Reduction

| Approach                          | Cost             | Quality          |
| --------------------------------- | ---------------- | ---------------- |
| **OpenAI text-embedding-3-small** | $0.02/1M tokens  | Good             |
| **Gemini text-embedding**         | Free (limited)   | Good             |
| **all-MiniLM-L6-v2 (local)**      | **$0 forever**   | Good enough      |
| **Cache embeddings in DB**        | One-time compute | Reuse infinitely |

**Decision:** Run `all-MiniLM-L6-v2` locally. Zero API cost. Cache all embeddings in ChromaDB.

Re-embed only when:

- User edits content significantly (>30% change)
- Document is re-uploaded with new content
- Never re-embed just because template changed

---

## Strategy 7: Self-Hosted Alternatives (Phase 3)

For maximum cost reduction, run models locally via Ollama:

| Task             | Cloud Model      | Local Alternative               | Quality | Cost     |
| ---------------- | ---------------- | ------------------------------- | ------- | -------- |
| OCR              | Gemini 2.5 Flash | Keep Gemini (no good local OCR) | —       | Keep     |
| Summarization    | Gemini           | Ollama + Llama 3.1 8B           | 80%     | **Free** |
| Field extraction | Gemini           | Ollama + Mistral 7B             | 75%     | **Free** |
| Classification   | Gemini           | Ollama + Phi-3 mini             | 85%     | **Free** |
| Embeddings       | OpenAI           | all-MiniLM-L6-v2                | 90%     | **Free** |

```python
# Hybrid approach: use local for cheap tasks, Gemini for OCR only
class HybridLLMService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434"  # Local Ollama
        self.gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

    async def generate(self, task_type: str, prompt: str):
        if task_type in ["summarize", "fill_simple_field", "classify"]:
            # FREE — use local Ollama
            return await self._ollama_generate("llama3.1:8b", prompt)
        else:
            # Paid — use Gemini for quality-critical tasks
            return await self._gemini_generate(prompt)
```

---

## Monthly Cost Projection by Phase

| Phase          | Docs/Month | OCR Cost | LLM Cost        | Infra Cost | Total      |
| -------------- | ---------- | -------- | --------------- | ---------- | ---------- |
| **MVP**        | 1,000      | $15      | $5              | $20 (VPS)  | **$40**    |
| **Growth**     | 10,000     | $75      | $30             | $50        | **$155**   |
| **Scale**      | 100,000    | $500     | $200            | $200       | **$900**   |
| **Enterprise** | 1,000,000  | $2,000   | $500 (+ Ollama) | $500       | **$3,000** |

**Key insight:** OCR is your #1 cost. Every optimization that avoids a Gemini OCR call directly affects your bottom line. The hybrid native+cached strategy saves 60-80% of OCR costs.
