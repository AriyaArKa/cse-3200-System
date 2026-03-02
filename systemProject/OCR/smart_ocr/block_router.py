"""
Block Router Module.
Handles block-level intelligent routing:
  - Splits text into logical blocks (paragraphs/layout segments)
  - Routes each block independently based on confidence
  - Only sends low-confidence blocks to Gemini
  - Merges corrected blocks back together
"""

import re
import logging
from typing import List, Optional

from .models import Block, LanguageType, RoutingDecision
from . import language_detector
from . import confidence_scorer
from . import correction_layer
from . import gemini_fallback

logger = logging.getLogger(__name__)


def split_into_blocks(text: str) -> List[str]:
    """
    Split text into logical blocks (paragraphs or layout segments).

    Strategy:
      - Split by double newlines (paragraph breaks)
      - Keep single-newline groups together
      - Minimum block size: 10 chars (merge tiny blocks with previous)
    """
    if not text or not text.strip():
        return []

    # Split by paragraph breaks (double newline)
    raw_blocks = re.split(r"\n\s*\n", text)

    # Filter and merge tiny blocks
    blocks = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) < 10 and blocks:
            # Merge tiny block with previous
            blocks[-1] = blocks[-1] + "\n" + block
        else:
            blocks.append(block)

    return blocks


def process_block(
    raw_text: str,
    block_id: str,
    ocr_confidence: float = 0.0,
    gemini_client=None,
    gemini_tracker=None,
) -> Block:
    """
    Process a single text block through the full pipeline:
      1. Language detection
      2. Confidence scoring
      3. Routing decision
      4. Correction (if needed)
      5. Gemini fallback (if still low confidence)

    Returns: Block with all metadata filled
    """
    block = Block(
        block_id=block_id,
        raw_text=raw_text,
    )

    if not raw_text.strip():
        block.confidence_score = 0.0
        block.routing_decision = RoutingDecision.ACCEPT.value
        return block

    # Step 1: Language detection
    lang_type, bangla_ratio, english_ratio = language_detector.detect_language(raw_text)
    block.detected_language_type = lang_type.value
    block.bangla_ratio = bangla_ratio
    block.english_ratio = english_ratio

    # Step 2: Confidence scoring
    confidence = confidence_scorer.calculate_confidence(
        text=raw_text,
        ocr_confidence=ocr_confidence,
        bangla_ratio=bangla_ratio,
        english_ratio=english_ratio,
        language_type=lang_type.value,
    )
    block.confidence_score = confidence

    # Step 3: Routing decision
    routing = confidence_scorer.get_routing_decision(confidence, lang_type.value)
    block.routing_decision = routing.value

    # Step 4: Apply based on routing
    if routing == RoutingDecision.ACCEPT:
        # High confidence → accept as-is
        block.corrected_text = raw_text
        block.gemini_used = False
        logger.debug(f"Block {block_id}: ACCEPT (conf={confidence:.3f})")

    elif routing == RoutingDecision.LOCAL_CORRECTION:
        # Medium confidence → apply correction layer
        corrected = correction_layer.correct_text(raw_text, lang_type.value)
        block.corrected_text = corrected

        # Re-calculate confidence after correction
        new_conf = confidence_scorer.calculate_confidence(
            text=corrected,
            ocr_confidence=ocr_confidence,
            bangla_ratio=bangla_ratio,
            english_ratio=english_ratio,
            language_type=lang_type.value,
        )
        block.confidence_score = new_conf

        # If still below threshold after correction → send to Gemini
        new_routing = confidence_scorer.get_routing_decision(new_conf, lang_type.value)
        if new_routing == RoutingDecision.GEMINI_FALLBACK and gemini_client:
            gemini_result = gemini_fallback.correct_block_with_gemini(
                corrected, lang_type.value, gemini_client
            )
            if gemini_result:
                block.corrected_text = gemini_result
                block.gemini_used = True
                if gemini_tracker:
                    gemini_tracker.record_block_correction()
            else:
                if gemini_tracker:
                    gemini_tracker.record_failure()
        else:
            block.gemini_used = False

        logger.debug(
            f"Block {block_id}: CORRECTED (conf={confidence:.3f}→{new_conf:.3f})"
        )

    elif routing == RoutingDecision.GEMINI_FALLBACK:
        # Low confidence → correction first, then Gemini
        corrected = correction_layer.correct_text(raw_text, lang_type.value)

        if gemini_client:
            gemini_result = gemini_fallback.correct_block_with_gemini(
                corrected, lang_type.value, gemini_client
            )
            if gemini_result:
                block.corrected_text = gemini_result
                block.gemini_used = True
                if gemini_tracker:
                    gemini_tracker.record_block_correction()
            else:
                block.corrected_text = corrected
                block.gemini_used = False
                if gemini_tracker:
                    gemini_tracker.record_failure()
        else:
            block.corrected_text = corrected
            block.gemini_used = False

        logger.debug(f"Block {block_id}: GEMINI FALLBACK (conf={confidence:.3f})")

    return block


def process_blocks(
    text: str,
    ocr_confidences: List[float] = None,
    gemini_client=None,
    gemini_tracker=None,
) -> List[Block]:
    """
    Split text into blocks and process each one.

    Args:
        text: Full text to split and process
        ocr_confidences: Per-block OCR confidences (if available)
        gemini_client: Gemini client for fallback
        gemini_tracker: Usage tracker

    Returns:
        List of processed Blocks
    """
    raw_blocks = split_into_blocks(text)
    if not raw_blocks:
        return []

    processed = []
    for i, raw_text in enumerate(raw_blocks):
        ocr_conf = (
            ocr_confidences[i] if ocr_confidences and i < len(ocr_confidences) else 0.5
        )
        block = process_block(
            raw_text=raw_text,
            block_id=f"block_{i + 1}",
            ocr_confidence=ocr_conf,
            gemini_client=gemini_client,
            gemini_tracker=gemini_tracker,
        )
        processed.append(block)

    return processed


def merge_blocks_text(blocks: List[Block]) -> str:
    """Merge processed blocks back into full text."""
    texts = []
    for block in blocks:
        text = block.corrected_text if block.corrected_text else block.raw_text
        if text.strip():
            texts.append(text.strip())
    return "\n\n".join(texts)
