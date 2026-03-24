"""
Result Merger Module for PerfectOCR.
Merges and votes between Gemini and GPT-4o OCR results.

Strategy:
  - Use Gemini as primary (better Bangla accuracy, more reliable)
  - For blocks where Gemini has low confidence, prefer GPT-4o's version
  - Merge tables and forms from both sources
  - Combine extraction notes
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def merge_page_results(
    gemini_result: Dict[str, Any],
    gpt_result: Dict[str, Any],
    page_num: int,
) -> Dict[str, Any]:
    """
    Merge OCR results from Gemini and GPT-4o for a single page.

    Strategy:
      1. Use Gemini as primary (better Bangla/handwriting accuracy)
      2. For low-confidence blocks, substitute GPT-4o's version
      3. Merge tables from both, preferring the one with more data
      4. Merge forms from both
      5. Use Gemini's full_text_reading_order (or GPT's if Gemini failed)

    Args:
        gemini_result: Gemini OCR output dict
        gpt_result: GPT-4o OCR output dict
        page_num: Page number

    Returns:
        Merged result dict
    """
    # Handle empty results
    gemini_blocks = gemini_result.get("content_blocks", [])
    gpt_blocks = gpt_result.get("content_blocks", [])

    # If one model completely failed, use the other
    if not gpt_blocks and gemini_blocks:
        logger.info(f"Page {page_num}: GPT-4o returned nothing, using Gemini only")
        _tag_blocks(gemini_blocks, "gemini")
        return gemini_result

    if not gemini_blocks and gpt_blocks:
        logger.info(f"Page {page_num}: Gemini returned nothing, using GPT-4o only")
        _tag_blocks(gpt_blocks, "gpt4o")
        return gpt_result

    if not gemini_blocks and not gpt_blocks:
        logger.warning(f"Page {page_num}: Both models returned nothing")
        return {
            "page_number": page_num,
            "content_blocks": [],
            "tables": [],
            "forms": [],
            "full_text_reading_order": "",
            "extraction_notes": ["Both OCR models returned no content"],
        }

    # ── Merge content blocks ────────────────────────────
    merged_blocks = _merge_content_blocks(gemini_blocks, gpt_blocks)

    # ── Merge tables ────────────────────────────────────
    merged_tables = _merge_tables(
        gemini_result.get("tables", []),
        gpt_result.get("tables", []),
    )

    # ── Merge forms ─────────────────────────────────────
    merged_forms = _merge_forms(
        gemini_result.get("forms", []),
        gpt_result.get("forms", []),
    )

    # ── Full text: prefer Gemini ────────────────────────
    full_text = gemini_result.get("full_text_reading_order", "") or gpt_result.get(
        "full_text_reading_order", ""
    )

    # ── Merge extraction notes ──────────────────────────
    notes = list(
        set(
            gpt_result.get("extraction_notes", [])
            + gemini_result.get("extraction_notes", [])
        )
    )

    merged = {
        "page_number": page_num,
        "content_blocks": merged_blocks,
        "tables": merged_tables,
        "forms": merged_forms,
        "full_text_reading_order": full_text,
        "extraction_notes": notes,
    }

    logger.info(
        f"Page {page_num}: Merged {len(gpt_blocks)} GPT + {len(gemini_blocks)} Gemini "
        f"→ {len(merged_blocks)} blocks"
    )

    return merged


def _tag_blocks(blocks: List[Dict], source: str):
    """Tag blocks with their source model."""
    for block in blocks:
        block["_source"] = source


def _merge_content_blocks(
    gemini_blocks: List[Dict],
    gpt_blocks: List[Dict],
) -> List[Dict]:
    """
    Merge content blocks from both models.
    Gemini is primary; for low-confidence blocks, substitute GPT-4o's version.
    """
    merged = []

    for i, gemini_block in enumerate(gemini_blocks):
        block = gemini_block.copy()
        block["_source"] = "gemini"

        # If Gemini block has low confidence and GPT-4o has a corresponding block
        gemini_conf = gemini_block.get("confidence", "high")
        if gemini_conf == "low" and i < len(gpt_blocks):
            gpt_conf = gpt_blocks[i].get("confidence", "high")
            if gpt_conf != "low":
                block = gpt_blocks[i].copy()
                block["_source"] = "gpt4o"
                logger.debug(
                    f"Block {i + 1}: Substituted GPT-4o (Gemini conf=low, GPT conf={gpt_conf})"
                )

        merged.append(block)

    # Add any extra GPT-4o blocks not covered by Gemini
    if len(gpt_blocks) > len(gemini_blocks):
        for j in range(len(gemini_blocks), len(gpt_blocks)):
            extra = gpt_blocks[j].copy()
            extra["_source"] = "gpt4o"
            extra["block_id"] = len(merged) + 1
            merged.append(extra)
            logger.debug(f"Block {j + 1}: Added extra block from GPT-4o")

    return merged


def _merge_tables(
    gemini_tables: List[Dict],
    gpt_tables: List[Dict],
) -> List[Dict]:
    """
    Merge tables from both models.
    Prefer the version with more rows/columns (more complete extraction).
    """
    if not gemini_tables and not gpt_tables:
        return []

    if not gpt_tables:
        return gemini_tables
    if not gemini_tables:
        return gpt_tables

    # If same number of tables, compare each pair
    if len(gemini_tables) == len(gpt_tables):
        merged = []
        for g_table, o_table in zip(gemini_tables, gpt_tables):
            g_cells = _count_table_cells(g_table)
            o_cells = _count_table_cells(o_table)
            if g_cells >= o_cells:
                merged.append(g_table)
            else:
                merged.append(o_table)
        return merged

    # Different number: use the one with more tables
    if len(gpt_tables) >= len(gemini_tables):
        return gpt_tables
    return gemini_tables


def _merge_forms(
    gemini_forms: List[Dict],
    gpt_forms: List[Dict],
) -> List[Dict]:
    """
    Merge forms: prefer the one with more filled fields.
    """
    if not gemini_forms and not gpt_forms:
        return []
    if not gpt_forms:
        return gemini_forms
    if not gemini_forms:
        return gpt_forms

    # Count filled fields
    g_filled = sum(
        1
        for form in gemini_forms
        for field in form.get("fields", [])
        if field.get("is_filled")
    )
    o_filled = sum(
        1
        for form in gpt_forms
        for field in form.get("fields", [])
        if field.get("is_filled")
    )

    return gpt_forms if o_filled >= g_filled else gemini_forms


def _count_table_cells(table: Dict) -> int:
    """Count total cells in a table."""
    data = table.get("data", [])
    if not data:
        return 0
    return sum(len(row) if isinstance(row, list) else 1 for row in data)
