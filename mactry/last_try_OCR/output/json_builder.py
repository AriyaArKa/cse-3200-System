"""
JSON Builder — Assembles final structured JSON output and writes files.
Handles per-page JSON, merged document JSON, and output directory management.
"""

import json
import logging
from pathlib import Path
from typing import List

from .. import config
from ..models import DocumentResult, PageResult
from ..nlp.unicode_validator import clean_text

logger = logging.getLogger(__name__)

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency in some environments
    np = None


def to_json_compatible(obj):
    """Recursively clean text and convert non-JSON-native values.

    Removes control characters (U+0001–U+001F) and CID references that arise
    from legacy font encodings (SutonnyMJ etc.).  Real Bangla Unicode chars
    (U+0980–U+09FF) are preserved unchanged.

    Also converts common non-serializable values (e.g., numpy scalars/arrays,
    Path objects) into standard Python JSON-compatible primitives.
    """
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, Path):
        return str(obj)
    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return [to_json_compatible(item) for item in obj.tolist()]
    if isinstance(obj, list):
        return [to_json_compatible(item) for item in obj]
    if isinstance(obj, tuple):
        return [to_json_compatible(item) for item in obj]
    if isinstance(obj, set):
        return [to_json_compatible(item) for item in sorted(obj, key=str)]
    if isinstance(obj, dict):
        return {k: to_json_compatible(v) for k, v in obj.items()}
    return obj


def ensure_output_dirs(doc_id: str) -> dict:
    """Create output directories for a document and return paths."""
    dirs = {
        "images": config.OUTPUT_IMAGES_DIR / doc_id,
        "jsons": config.JSON_OUTPUT_DIR / doc_id,
        "merged": config.MERGED_OUTPUT_DIR,
        "texts": config.TEXT_OUTPUT_DIR,
        "logs": config.LOG_DIR,
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def save_page_json(page_result: PageResult, output_dir: Path):
    """Save a single page's result as JSON."""
    path = output_dir / f"page_{page_result.page_number}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_json_compatible(page_result.to_dict()), f, ensure_ascii=False, indent=2)
    logger.info("Saved page JSON: %s", path)


def save_document_text(doc_result: DocumentResult, output_dir: Path, doc_id: str) -> Path:
    """Save extracted text as a page-grouped plain text file."""
    txt_path = output_dir / f"{doc_id}.txt"
    lines: list[str] = []
    for page in sorted(doc_result.pages, key=lambda p: p.page_number):
        lines.append(f"Page {page.page_number}")
        lines.append("=" * len(lines[-1]))

        page_text = (page.full_text or "").strip()
        if not page_text:
            page_text = "\n".join(
                (b.text or "").strip() for b in page.content_blocks if (b.text or "").strip()
            ).strip()

        lines.append(clean_text(page_text) if page_text else "[NO_TEXT_EXTRACTED]")
        lines.append("")

    txt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    logger.info("Saved extracted TXT: %s", txt_path)
    return txt_path


def save_document_json(doc_result: DocumentResult, doc_id: str):
    """Save per-page + merged JSON, then best-effort corpus output."""
    dirs = ensure_output_dirs(doc_id)

    # Save per-page JSONs
    for page in doc_result.pages:
        save_page_json(page, dirs["jsons"])

    # Save merged document JSON
    merged_path = dirs["merged"] / f"{doc_id}.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(to_json_compatible(doc_result.to_dict()), f, ensure_ascii=False, indent=2)
    logger.info("Saved merged JSON: %s", merged_path)

    save_document_text(doc_result, dirs["texts"], doc_id)

    try:
        domain = doc_result.pages[0].domain if doc_result.pages else "unknown"
        save_corpus_parquet(doc_result, doc_id, domain=domain)
    except Exception as e:
        logger.warning("Corpus save failed for doc_id=%s: %s", doc_id, e)

    return merged_path


def load_document_json(doc_id: str) -> dict | None:
    """Load a previously saved document JSON."""
    path = config.MERGED_OUTPUT_DIR / f"{doc_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _corpus_paths() -> dict:
    """Return corpus directory and file paths."""
    corpus_dir = config.OUTPUT_DIR / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": corpus_dir,
        "parquet": corpus_dir / "corpus.parquet",
        "jsonl": corpus_dir / "corpus.jsonl",
        "stats": corpus_dir / "corpus_stats.json",
    }


def _safe_write_stats(records: list[dict], stats_path: Path) -> None:
    """Write corpus summary statistics as UTF-8 JSON."""
    total_records = len(records)
    by_domain: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_engine: dict[str, int] = {}

    total_confidence = 0.0
    total_words = 0
    total_chars = 0

    for r in records:
        domain = str(r.get("domain", "unknown") or "unknown")
        tier = str(r.get("confidence_tier", "bronze") or "bronze")
        engine = str(r.get("engine", "unknown") or "unknown")

        by_domain[domain] = by_domain.get(domain, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        by_engine[engine] = by_engine.get(engine, 0) + 1

        total_confidence += float(r.get("confidence_score", 0.0) or 0.0)
        total_words += int(r.get("word_count", 0) or 0)
        total_chars += int(r.get("char_count", 0) or 0)

    stats = {
        "total_records": total_records,
        "by_domain": by_domain,
        "by_tier": by_tier,
        "by_engine": by_engine,
        "avg_confidence": round(total_confidence / total_records, 4)
        if total_records
        else 0.0,
        "total_words": total_words,
        "total_chars": total_chars,
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def _load_all_records_for_stats(paths: dict) -> list[dict]:
    """Load corpus records from parquet if possible, else from jsonl."""
    parquet_path = paths["parquet"]
    jsonl_path = paths["jsonl"]

    if parquet_path.exists():
        try:
            import pandas as pd

            return pd.read_parquet(parquet_path).to_dict(orient="records")
        except Exception as e:
            logger.warning("Failed reading parquet for stats: %s", e)

    records: list[dict] = []
    if jsonl_path.exists():
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    records.append(json.loads(line))
        except Exception as e:
            logger.warning("Failed reading JSONL for stats: %s", e)
    return records


def save_corpus_parquet(doc_result: DocumentResult, doc_id: str, domain: str = "unknown"):
    """Append page-level corpus records to parquet, fallback to JSONL if needed."""
    paths = _corpus_paths()
    parquet_path = paths["parquet"]
    jsonl_path = paths["jsonl"]
    stats_path = paths["stats"]

    records: list[dict] = []
    for page in doc_result.pages:
        page.domain = page.domain or domain
        rec = page.to_corpus_record()
        rec["doc_id"] = doc_id
        records.append(rec)

    if not records:
        logger.info("No pages available for corpus export (doc_id=%s)", doc_id)
        return

    try:
        import pandas as pd

        df_new = pd.DataFrame(records)
        if parquet_path.exists():
            try:
                df_existing = pd.read_parquet(parquet_path)
                df_all = pd.concat([df_existing, df_new], ignore_index=True)
            except Exception as e:
                logger.warning("Reading existing parquet failed, rewriting from new rows only: %s", e)
                df_all = df_new
        else:
            df_all = df_new

        df_all.to_parquet(parquet_path, index=False, engine="pyarrow")
        logger.info("Corpus parquet updated: %s (%d total rows)", parquet_path, len(df_all))
    except Exception as e:
        logger.warning("Parquet save unavailable; using JSONL fallback: %s", e)
        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(to_json_compatible(rec), ensure_ascii=False) + "\n")
            logger.info("Corpus JSONL updated: %s (+%d rows)", jsonl_path, len(records))
        except Exception as jsonl_err:
            logger.warning("Corpus JSONL fallback also failed: %s", jsonl_err)
            return

    try:
        all_records = _load_all_records_for_stats(paths)
        _safe_write_stats(all_records, stats_path)
    except Exception as e:
        logger.warning("Failed to update corpus stats: %s", e)


def rebuild_corpus_from_json_outputs() -> dict:
    """Rebuild corpus files from existing page JSON outputs (best effort)."""
    paths = _corpus_paths()
    all_records: list[dict] = []

    try:
        for doc_dir in sorted(config.JSON_OUTPUT_DIR.glob("*")):
            if not doc_dir.is_dir():
                continue
            doc_id = doc_dir.name
            for page_file in sorted(doc_dir.glob("page_*.json")):
                try:
                    with open(page_file, "r", encoding="utf-8") as f:
                        page = json.load(f)

                    extraction = page.get("extraction", {}) or {}
                    full_text = page.get("full_text", "") or ""
                    bn_chars = sum(1 for ch in full_text if 0x0980 <= ord(ch) <= 0x09FF)
                    total_chars = max(len(full_text), 1)
                    language_ratio_bn = bn_chars / total_chars

                    confidence_score = float(extraction.get("confidence_score", 0.0) or 0.0)
                    verified = bool(page.get("verified", False))
                    if confidence_score >= 0.85 and verified:
                        tier = "gold"
                    elif confidence_score >= 0.65:
                        tier = "silver"
                    else:
                        tier = "bronze"

                    all_records.append(
                        {
                            "doc_id": doc_id,
                            "page_number": int(page.get("page_number", 0) or 0),
                            "full_text": full_text,
                            "source_image_path": page.get("source_image_path", "") or "",
                            "engine": extraction.get("engine", "unknown") or "unknown",
                            "confidence_score": confidence_score,
                            "verified": verified,
                            "domain": page.get("domain", "unknown") or "unknown",
                            "confidence_tier": tier,
                            "language_ratio_bn": round(language_ratio_bn, 4),
                            "has_table": bool(page.get("tables")),
                            "has_image": bool(page.get("images")),
                            "word_count": len([w for w in full_text.split() if w.strip()]),
                            "char_count": len(full_text),
                        }
                    )
                except Exception as e:
                    logger.warning("Skipping corpus rebuild for %s: %s", page_file, e)
    except Exception as e:
        logger.warning("Failed to scan JSON outputs for corpus rebuild: %s", e)

    if not all_records:
        stats = {
            "total_records": 0,
            "by_domain": {},
            "by_tier": {},
            "by_engine": {},
            "avg_confidence": 0.0,
            "total_words": 0,
            "total_chars": 0,
        }
        try:
            with open(paths["stats"], "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to write empty corpus stats: %s", e)
        return stats

    try:
        import pandas as pd

        df = pd.DataFrame(all_records)
        df.to_parquet(paths["parquet"], index=False, engine="pyarrow")
        logger.info("Rebuilt corpus parquet with %d rows", len(df))
    except Exception as e:
        logger.warning("Parquet rebuild failed; falling back to JSONL: %s", e)
        try:
            with open(paths["jsonl"], "w", encoding="utf-8") as f:
                for rec in all_records:
                    f.write(json.dumps(to_json_compatible(rec), ensure_ascii=False) + "\n")
        except Exception as jsonl_err:
            logger.warning("JSONL rebuild failed: %s", jsonl_err)

    try:
        _safe_write_stats(all_records, paths["stats"])
        with open(paths["stats"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to write/read rebuilt corpus stats: %s", e)
        return {
            "total_records": len(all_records),
            "by_domain": {},
            "by_tier": {},
            "by_engine": {},
            "avg_confidence": 0.0,
            "total_words": sum(int(r.get("word_count", 0) or 0) for r in all_records),
            "total_chars": sum(int(r.get("char_count", 0) or 0) for r in all_records),
        }
