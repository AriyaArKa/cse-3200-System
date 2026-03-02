"""
Main Pipeline Orchestrator.
Coordinates the full Smart OCR pipeline:

  Upload PDF
  → Page classification (native text vs OCR needed)
  → Native text extraction OR Image conversion (per-page)
  → PaddleOCR (if image) → Block segmentation
  → Language detection per block
  → Composite confidence scoring
  → Correction layer
  → Selective Gemini fallback (block-level only)
  → Merge structured output
  → Save JSON (old format compatible)
"""

import sys
import time
import uuid
import json
import logging
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any

from . import config
from .models import (
    Block,
    PageResult,
    DocumentResult,
    LanguageType,
    SourceType,
    RoutingDecision,
)
from .pdf_processor import SmartPDFProcessor, PageClassification
from .ocr_engine import PaddleOCREngine
from . import language_detector
from . import confidence_scorer
from . import correction_layer
from . import block_router
from . import gemini_fallback
from .gemini_fallback import GeminiUsageTracker
from . import output_handler

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class PipelineProgress:
    """Progress tracker for the pipeline — can be hooked to UI callbacks."""

    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.current_step = ""
        self.current_detail = ""
        self.progress = 0.0  # 0.0 to 1.0

    def update(self, step: str, detail: str = "", progress: float = 0.0):
        self.current_step = step
        self.current_detail = detail
        self.progress = progress
        if self.callback:
            self.callback(step, detail, progress)
        logger.info(f"[{step}] {detail} ({progress:.0%})")


class SmartOCRPipeline:
    """
    Production-grade PDF OCR pipeline.
    Bangla-first, cost-efficient, confidence-driven, block-level routing.
    """

    def __init__(
        self,
        pdf_path: str,
        output_dir: str = None,
        progress_callback: Optional[Callable] = None,
        use_paddle: bool = True,
        force_gemini_all: bool = False,
    ):
        """
        Args:
            pdf_path: Path to PDF file
            output_dir: Base output directory (defaults to config)
            progress_callback: fn(step, detail, progress) for UI updates
            use_paddle: Use PaddleOCR (True) or skip to Gemini (False)
            force_gemini_all: Force Gemini for all pages (like old method)
        """
        self.pdf_path = pdf_path
        self.run_id = uuid.uuid4().hex[:8]
        self.use_paddle = use_paddle
        self.force_gemini_all = force_gemini_all

        # Output directories
        base_output = (
            Path(output_dir) if output_dir else config.MERGED_OUTPUT_DIR.parent
        )
        self.images_dir = base_output / "output_images" / self.run_id
        self.jsons_dir = base_output / "output_jsons" / self.run_id
        self.merged_dir = base_output / "merged_outputs"

        # Components
        self.pdf_processor = SmartPDFProcessor(pdf_path, str(self.images_dir))
        self.ocr_engine = PaddleOCREngine() if use_paddle else None
        self.gemini_tracker = GeminiUsageTracker()
        self.progress = PipelineProgress(progress_callback)

        # Gemini client (lazy init)
        self._gemini_client = None

    @property
    def gemini_client(self):
        """Lazy Gemini client initialization."""
        if self._gemini_client is None:
            try:
                from google import genai

                self._gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"Gemini client init failed: {e}")
        return self._gemini_client

    def run(self) -> DocumentResult:
        """
        Execute the full pipeline.

        Returns:
            DocumentResult with all processed pages
        """
        start_time = time.time()
        pdf_name = Path(self.pdf_path).name

        logger.info(f"{'='*60}")
        logger.info(f"Smart OCR Pipeline — {pdf_name}")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"{'='*60}")

        # ===== STEP 1: Classify Pages =====
        self.progress.update("Classifying", "Analyzing PDF pages...", 0.05)
        classifications = self.pdf_processor.classify_pages(
            progress_callback=lambda p, t, msg: self.progress.update(
                "Classifying", f"Page {p}/{t}", p / t * 0.15
            )
        )

        total_pages = len(classifications)
        native_pages = sum(1 for c in classifications if c.has_native_text)
        ocr_pages = total_pages - native_pages
        logger.info(
            f"Pages: {total_pages} total, {native_pages} native, {ocr_pages} need OCR"
        )

        # ===== STEP 2: Process Each Page =====
        page_results: List[PageResult] = []
        saved_json_files: List[str] = []

        for i, classification in enumerate(classifications):
            page_num = classification.page_number
            self.progress.update(
                "Processing",
                f"Page {page_num}/{total_pages}",
                0.15 + (i / total_pages * 0.70),
            )

            page_start = time.time()

            if self.force_gemini_all:
                # Force mode: convert all to images, send to Gemini (like old method)
                page_result = self._process_page_gemini_only(classification)
            elif classification.has_native_text:
                # Native text available → process text blocks
                page_result = self._process_native_page(classification)
            else:
                # OCR needed → image-based processing
                page_result = self._process_ocr_page(classification)

            page_result.processing_time_ms = (time.time() - page_start) * 1000
            page_results.append(page_result)

            # Save individual page JSON
            json_path = output_handler.save_page_json(
                page_result, self.jsons_dir, page_num, self.run_id
            )
            saved_json_files.append(str(json_path))

        # ===== STEP 3: Build Document Result =====
        self.progress.update("Merging", "Building final output...", 0.90)

        doc_result = self._build_document_result(pdf_name, page_results)
        doc_result.processing_time_ms = (time.time() - start_time) * 1000

        # ===== STEP 4: Save Merged Output =====
        self.progress.update("Saving", "Writing merged JSON...", 0.95)

        merged_path = output_handler.save_merged_json(
            doc_result, self.merged_dir, pdf_name, self.run_id, use_old_format=True
        )

        self.progress.update(
            "Complete", f"Done in {doc_result.processing_time_ms:.0f}ms", 1.0
        )

        logger.info(f"\n{'='*60}")
        logger.info(f"Pipeline Complete!")
        logger.info(f"  Pages processed: {total_pages}")
        logger.info(f"  Native text pages: {native_pages}")
        logger.info(f"  OCR pages: {ocr_pages}")
        logger.info(f"  Gemini API calls: {self.gemini_tracker.total_calls}")
        logger.info(f"  Cache hits: {self.gemini_tracker.cache_hits}")
        logger.info(f"  Processing time: {doc_result.processing_time_ms:.0f}ms")
        logger.info(f"  Output: {merged_path}")
        logger.info(f"{'='*60}")

        return doc_result

    def _process_native_page(self, classification: PageClassification) -> PageResult:
        """Process a page where native text extraction succeeded."""
        page_num = classification.page_number
        logger.info(f"Page {page_num}: Processing with native text")

        # Split into blocks and process
        blocks = block_router.process_blocks(
            text=classification.native_text,
            gemini_client=self.gemini_client,
            gemini_tracker=self.gemini_tracker,
        )

        # Calculate page-level stats
        page_confidence = self._calculate_page_confidence(blocks)
        lang_dist = self._calculate_page_language_dist(blocks)

        return PageResult(
            page_id=page_num,
            source_type=SourceType.NATIVE_TEXT.value,
            blocks=blocks,
            page_confidence_score=page_confidence,
            page_language_distribution=lang_dist,
            native_text_available=True,
        )

    def _process_ocr_page(self, classification: PageClassification) -> PageResult:
        """Process a page that needs OCR (image-based)."""
        page_num = classification.page_number
        image_path = classification.image_path
        logger.info(f"Page {page_num}: Processing with OCR (image={image_path})")

        if not image_path:
            logger.error(f"Page {page_num}: No image available for OCR")
            return PageResult(page_id=page_num, source_type=SourceType.OCR.value)

        source_type = SourceType.OCR.value

        # Try PaddleOCR first
        if self.use_paddle and self.ocr_engine:
            try:
                ocr_blocks = self.ocr_engine.ocr_image(image_path, lang_hint="auto")

                if ocr_blocks:
                    # Convert OCR blocks to text and process
                    full_text = self.ocr_engine.get_full_text(ocr_blocks)
                    avg_conf = self.ocr_engine.get_average_confidence(ocr_blocks)
                    ocr_confs = [b.confidence for b in ocr_blocks]

                    logger.info(
                        f"Page {page_num}: PaddleOCR found {len(ocr_blocks)} blocks "
                        f"(avg_conf={avg_conf:.3f})"
                    )

                    # If PaddleOCR confidence is very low → fall back to Gemini for whole page
                    if avg_conf < 0.3:
                        logger.info(
                            f"Page {page_num}: PaddleOCR confidence too low, using Gemini"
                        )
                        return self._process_page_gemini_only(classification)

                    # Process through block router
                    blocks = block_router.process_blocks(
                        text=full_text,
                        ocr_confidences=ocr_confs,
                        gemini_client=self.gemini_client,
                        gemini_tracker=self.gemini_tracker,
                    )

                    # If native text was partially available, mark as hybrid
                    if classification.native_text:
                        source_type = SourceType.HYBRID.value

                    page_confidence = self._calculate_page_confidence(blocks)
                    lang_dist = self._calculate_page_language_dist(blocks)

                    return PageResult(
                        page_id=page_num,
                        source_type=source_type,
                        blocks=blocks,
                        page_confidence_score=page_confidence,
                        page_language_distribution=lang_dist,
                        image_path=image_path,
                    )

            except Exception as e:
                logger.warning(
                    f"Page {page_num}: PaddleOCR failed: {e}. Falling back to Gemini."
                )

        # PaddleOCR not available or failed → Gemini extraction
        return self._process_page_gemini_only(classification)

    def _process_page_gemini_only(
        self, classification: PageClassification
    ) -> PageResult:
        """Process a page using Gemini only (fallback or forced mode)."""
        page_num = classification.page_number
        image_path = classification.image_path

        # If no image, convert now
        if not image_path:
            image_path = self.pdf_processor._convert_page_to_image(
                classification.page_number - 1, self.run_id
            )
            classification.image_path = image_path

        if not image_path:
            logger.error(f"Page {page_num}: Cannot process — no image")
            return PageResult(page_id=page_num, source_type=SourceType.OCR.value)

        logger.info(f"Page {page_num}: Gemini extraction")

        # Use Gemini for full page extraction (like old method)
        result_text = gemini_fallback.extract_page_with_gemini(
            image_path, self.gemini_client
        )
        self.gemini_tracker.record_page_extraction()

        if result_text:
            # Create a single block with the Gemini result
            lang_type, bn_ratio, en_ratio = language_detector.detect_language(
                result_text
            )

            block = Block(
                block_id="block_1",
                detected_language_type=lang_type.value,
                bangla_ratio=bn_ratio,
                english_ratio=en_ratio,
                raw_text=result_text,
                corrected_text=result_text,
                confidence_score=0.90,  # Gemini results are generally reliable
                routing_decision=RoutingDecision.GEMINI_FALLBACK.value,
                gemini_used=True,
            )

            lang_dist = language_detector.calculate_page_language_distribution(
                [(lang_type, bn_ratio, en_ratio)]
            )

            return PageResult(
                page_id=page_num,
                source_type=SourceType.OCR.value,
                blocks=[block],
                page_confidence_score=0.90,
                page_language_distribution=lang_dist,
                image_path=image_path,
            )
        else:
            self.gemini_tracker.record_failure()
            return PageResult(
                page_id=page_num,
                source_type=SourceType.OCR.value,
                image_path=image_path,
            )

    def _calculate_page_confidence(self, blocks: List[Block]) -> float:
        """Calculate average confidence across page blocks."""
        if not blocks:
            return 0.0
        total = sum(b.confidence_score for b in blocks)
        return round(total / len(blocks), 4)

    def _calculate_page_language_dist(self, blocks: List[Block]) -> dict:
        """Calculate language distribution across page blocks."""
        langs = []
        for b in blocks:
            try:
                lt = LanguageType(b.detected_language_type)
            except ValueError:
                lt = LanguageType.UNKNOWN
            langs.append((lt, b.bangla_ratio, b.english_ratio))
        return language_detector.calculate_page_language_distribution(langs)

    def _build_document_result(
        self, pdf_name: str, page_results: List[PageResult]
    ) -> DocumentResult:
        """Build the final DocumentResult."""
        # Overall confidence
        if page_results:
            overall_conf = sum(p.page_confidence_score for p in page_results) / len(
                page_results
            )
        else:
            overall_conf = 0.0

        # Language distribution summary
        all_langs = []
        for p in page_results:
            for b in p.blocks:
                try:
                    lt = LanguageType(b.detected_language_type)
                except ValueError:
                    lt = LanguageType.UNKNOWN
                all_langs.append((lt, b.bangla_ratio, b.english_ratio))

        lang_summary = language_detector.calculate_page_language_distribution(all_langs)

        return DocumentResult(
            document_name=pdf_name,
            total_pages=len(page_results),
            pages=page_results,
            overall_confidence=round(overall_conf, 4),
            gemini_usage_summary=self.gemini_tracker.to_dict(),
            language_distribution_summary=lang_summary,
        )


def run_pipeline(
    pdf_path: str,
    output_dir: str = None,
    progress_callback: Callable = None,
    use_paddle: bool = True,
    force_gemini_all: bool = False,
) -> DocumentResult:
    """
    Convenience function to run the full pipeline.

    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory (default: smart_ocr_output/)
        progress_callback: fn(step, detail, progress) for progress updates
        use_paddle: Use PaddleOCR (default True)
        force_gemini_all: Force Gemini for all pages (default False)

    Returns:
        DocumentResult
    """
    pipeline = SmartOCRPipeline(
        pdf_path=pdf_path,
        output_dir=output_dir,
        progress_callback=progress_callback,
        use_paddle=use_paddle,
        force_gemini_all=force_gemini_all,
    )
    return pipeline.run()
