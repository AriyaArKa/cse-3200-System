"""
Main Pipeline Orchestrator for PerfectOCR.

Coordinates the full dual-model OCR pipeline:

  Upload PDF
  → Convert pages to images (PyMuPDF)
  → Run Gemini OCR on each page
  → Run GPT-4o OCR on each page
  → Merge/Vote results (per-page, per-block)
  → Apply Bangla text correction
  → Save structured JSON output

Strategies:
  - dual:          Both models → merge best results
  - gpt4o_primary: GPT-4o first → Gemini only for failed pages
  - gemini_primary: Gemini first → GPT-4o only for failed pages
  - gpt4o_only:    GPT-4o only
  - gemini_only:   Gemini only
"""

import sys
import time
import uuid
import json
import logging
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any

from . import config
from .models import ContentBlock, PageResult, DocumentMetadata, DocumentResult
from .pdf_processor import PDFProcessor, PageImage
from .ocr_engines import GeminiOCREngine, GPT4oOCREngine, OCRUsageTracker
from . import merger
from . import correction
from . import output_handler

# Try to import fast OCR
try:
    from .fast_ocr import FastOCREngine, should_use_ai_ocr, TESSERACT_AVAILABLE
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("Fast OCR not available. Install pytesseract for optimization.")

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class PipelineProgress:
    """Progress tracker — hooks into UI callbacks."""

    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback

    def update(self, step: str, detail: str = "", progress: float = 0.0):
        if self.callback:
            self.callback(step, detail, progress)
        logger.info(f"[{step}] {detail} ({progress:.0%})")


class PerfectOCRPipeline:
    """
    Dual-model OCR pipeline.
    GPT-4o + Gemini → merge → Bangla correction → structured JSON.
    """

    def __init__(
        self,
        pdf_path: str,
        output_dir: str = None,
        strategy: str = None,
        enable_correction: bool = True,
        dpi: int = None,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Args:
            pdf_path: Path to PDF file
            output_dir: Base output directory
            strategy: OCR strategy (dual, gpt4o_primary, gemini_primary, gpt4o_only, gemini_only)
            enable_correction: Enable Bangla post-correction
            dpi: Image resolution for conversion
            progress_callback: fn(step, detail, progress) for UI updates
        """
        self.pdf_path = pdf_path
        self.run_id = uuid.uuid4().hex[:8]
        self.strategy = strategy or config.DEFAULT_STRATEGY
        self.enable_correction = enable_correction
        self.dpi = dpi or config.DPI

        # Output directories
        base_output = (
            Path(output_dir) if output_dir else config.MERGED_OUTPUT_DIR.parent
        )
        self.images_dir = base_output / "output_images" / self.run_id
        self.jsons_dir = base_output / "output_jsons" / self.run_id
        self.merged_dir = base_output / "merged_outputs"

        # Components
        self.pdf_processor = PDFProcessor(pdf_path, str(self.images_dir))
        self.tracker = OCRUsageTracker()
        self.progress = PipelineProgress(progress_callback)

        # Lazy-init OCR engines
        self._gemini_engine = None
        self._gpt4o_engine = None
        self._fast_ocr_engine = None

        # Enable fast OCR optimization if available
        self.use_fast_ocr_first = (
            TESSERACT_AVAILABLE and self.strategy == "gemini_primary"
        )

    @property
    def gemini_engine(self) -> GeminiOCREngine:
        if self._gemini_engine is None:
            self._gemini_engine = GeminiOCREngine()
        return self._gemini_engine

    @property
    def gpt4o_engine(self) -> GPT4oOCREngine:
        if self._gpt4o_engine is None:
            self._gpt4o_engine = GPT4oOCREngine()
        return self._gpt4o_engine

    @property
    def fast_ocr_engine(self):
        if self._fast_ocr_engine is None and TESSERACT_AVAILABLE:
            try:
                self._fast_ocr_engine = FastOCREngine()
            except Exception as e:
                logger.warning(f"Failed to init FastOCR: {e}")
        return self._fast_ocr_engine

    def run(self) -> DocumentResult:
        """
        Execute the full pipeline.

        Returns:
            DocumentResult with all processed pages
        """
        start_time = time.time()
        pdf_name = Path(self.pdf_path).name

        logger.info(f"{'=' * 60}")
        logger.info(f"PerfectOCR Pipeline — {pdf_name}")
        logger.info(f"Strategy: {self.strategy} | Run ID: {self.run_id}")
        logger.info(f"{'=' * 60}")

        # ===== STEP 1: Convert PDF to Images =====
        self.progress.update("Converting", "PDF → Images...", 0.05)
        page_images = self.pdf_processor.convert_to_images(
            dpi=self.dpi,
            run_id=self.run_id,
            progress_callback=lambda p, t, msg: self.progress.update(
                "Converting", msg, 0.05 + (p / t * 0.15)
            ),
        )
        total_pages = len(page_images)

        # ===== STEP 2: Run OCR on each page =====
        page_results: List[PageResult] = []

        for i, page_img in enumerate(page_images):
            pnum = page_img.page_number
            self.progress.update(
                "OCR",
                f"Page {pnum}/{total_pages} ({self.strategy})",
                0.20 + (i / total_pages * 0.50),
            )

            page_start = time.time()
            page_data = self._process_page(page_img)

            # ===== STEP 3: Bangla Correction =====
            if self.enable_correction and config.ENABLE_BANGLA_CORRECTION:
                self.progress.update(
                    "Correction",
                    f"Page {pnum}/{total_pages}",
                    0.70 + (i / total_pages * 0.15),
                )
                page_data = self._apply_correction(page_data, pnum)

            # Build PageResult
            page_result = self._build_page_result(page_data, page_img, page_start)
            page_results.append(page_result)

            # Save individual page JSON
            output_handler.save_page_json(page_data, self.jsons_dir, pnum, self.run_id)

        # ===== STEP 4: Build Document Result =====
        self.progress.update("Merging", "Building final output...", 0.90)

        models_used = self._get_models_used()

        doc_metadata = DocumentMetadata(
            source=pdf_name,
            total_pages=total_pages,
            models_used=models_used,
        )

        doc_result = DocumentResult(
            document=doc_metadata,
            pages=page_results,
            processing_time_ms=(time.time() - start_time) * 1000,
            strategy_used=self.strategy,
        )
        doc_result.detect_document_features()

        # ===== STEP 5: Save Merged Output =====
        self.progress.update("Saving", "Writing merged JSON...", 0.95)
        output_handler.save_document_json(
            doc_result, self.merged_dir, pdf_name, self.run_id
        )

        self.progress.update(
            "Complete",
            f"Done in {doc_result.processing_time_ms:.0f}ms",
            1.0,
        )

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Pipeline Complete!")
        logger.info(f"  Pages: {total_pages}")
        logger.info(f"  Strategy: {self.strategy}")
        logger.info(f"  API calls: {self.tracker.to_dict()}")
        logger.info(f"  Time: {doc_result.processing_time_ms:.0f}ms")
        logger.info(f"{'=' * 60}")

        return doc_result

    def _process_page(self, page_img: PageImage) -> Dict[str, Any]:
        """Process a single page based on the chosen strategy."""
        pnum = page_img.page_number
        b64 = page_img.image_b64

        # ===== HYBRID: Fast OCR first (Tesseract) for gemini_primary strategy =====
        if self.use_fast_ocr_first and self.fast_ocr_engine:
            try:
                logger.info(f"  Page {pnum}: Running fast OCR (Tesseract)...")
                fast_result = self.fast_ocr_engine.extract_page(b64, pnum)

                # Check if we need AI OCR
                if not should_use_ai_ocr(fast_result):
                    # Tesseract result is good enough - skip AI models
                    logger.info(f"  Page {pnum}: Using Tesseract result (no AI needed)")
                    for block in fast_result.get("content_blocks", []):
                        block["_source"] = "tesseract"
                    self.tracker.record_tesseract_only()
                    return fast_result
                else:
                    logger.info(
                        f"  Page {pnum}: Tesseract not sufficient, using AI OCR..."
                    )
            except Exception as e:
                logger.warning(
                    f"  Page {pnum}: Fast OCR failed: {e}, falling back to AI"
                )

        # ===== Standard AI OCR strategies =====
        if self.strategy == "dual":
            return self._process_dual(b64, pnum)
        elif self.strategy == "gpt4o_primary":
            return self._process_gpt4o_primary(b64, pnum)
        elif self.strategy == "gemini_primary":
            return self._process_gemini_primary(b64, pnum)
        elif self.strategy == "gpt4o_only":
            return self._process_single(self.gpt4o_engine, "gpt4o", b64, pnum)
        elif self.strategy == "gemini_only":
            return self._process_single(self.gemini_engine, "gemini", b64, pnum)
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', falling back to dual")
            return self._process_dual(b64, pnum)

    def _process_dual(self, b64: str, page_num: int) -> Dict[str, Any]:
        """Run both models and merge results."""
        # Gemini
        logger.info(f"  Page {page_num}: Running Gemini OCR...")
        try:
            gemini_out = self.gemini_engine.extract_page(b64, page_num)
            self.tracker.record_gemini_call(success=True)
        except Exception as e:
            logger.warning(f"  Page {page_num}: Gemini failed: {e}")
            gemini_out = self._empty_result(page_num, f"Gemini failed: {e}")
            self.tracker.record_gemini_call(success=False)

        # GPT-4o
        logger.info(f"  Page {page_num}: Running GPT-4o OCR...")
        try:
            gpt_out = self.gpt4o_engine.extract_page(b64, page_num)
            self.tracker.record_gpt4o_call(success=True)
        except Exception as e:
            logger.warning(f"  Page {page_num}: GPT-4o failed: {e}")
            gpt_out = self._empty_result(page_num, f"GPT-4o failed: {e}")
            self.tracker.record_gpt4o_call(success=False)

        # Merge
        logger.info(f"  Page {page_num}: Merging results...")
        return merger.merge_page_results(gemini_out, gpt_out, page_num)

    def _process_gpt4o_primary(self, b64: str, page_num: int) -> Dict[str, Any]:
        """GPT-4o first, Gemini fallback for failed pages."""
        logger.info(f"  Page {page_num}: Running GPT-4o (primary)...")
        try:
            result = self.gpt4o_engine.extract_page(b64, page_num)
            self.tracker.record_gpt4o_call(success=True)

            # Check if result is usable
            if result.get("content_blocks"):
                for block in result["content_blocks"]:
                    block["_source"] = "gpt4o"
                return result
        except Exception as e:
            logger.warning(f"  Page {page_num}: GPT-4o failed: {e}")
            self.tracker.record_gpt4o_call(success=False)

        # Fallback to Gemini
        logger.info(f"  Page {page_num}: Falling back to Gemini...")
        try:
            result = self.gemini_engine.extract_page(b64, page_num)
            self.tracker.record_gemini_call(success=True)
            for block in result.get("content_blocks", []):
                block["_source"] = "gemini"
            return result
        except Exception as e:
            logger.error(f"  Page {page_num}: Gemini also failed: {e}")
            self.tracker.record_gemini_call(success=False)
            return self._empty_result(page_num, f"Both models failed: {e}")

    def _process_gemini_primary(self, b64: str, page_num: int) -> Dict[str, Any]:
        """Gemini first, GPT-4o fallback for failed pages."""
        logger.info(f"  Page {page_num}: Running Gemini (primary)...")
        try:
            result = self.gemini_engine.extract_page(b64, page_num)
            self.tracker.record_gemini_call(success=True)

            if result.get("content_blocks"):
                for block in result["content_blocks"]:
                    block["_source"] = "gemini"
                return result
        except Exception as e:
            logger.warning(f"  Page {page_num}: Gemini failed: {e}")
            self.tracker.record_gemini_call(success=False)

        # Fallback to GPT-4o
        logger.info(f"  Page {page_num}: Falling back to GPT-4o...")
        try:
            result = self.gpt4o_engine.extract_page(b64, page_num)
            self.tracker.record_gpt4o_call(success=True)
            for block in result.get("content_blocks", []):
                block["_source"] = "gpt4o"
            return result
        except Exception as e:
            logger.error(f"  Page {page_num}: GPT-4o also failed: {e}")
            self.tracker.record_gpt4o_call(success=False)
            return self._empty_result(page_num, f"Both models failed: {e}")

    def _process_single(
        self, engine, name: str, b64: str, page_num: int
    ) -> Dict[str, Any]:
        """Run a single model."""
        logger.info(f"  Page {page_num}: Running {name}...")
        try:
            result = engine.extract_page(b64, page_num)
            if name == "gemini":
                self.tracker.record_gemini_call(success=True)
            else:
                self.tracker.record_gpt4o_call(success=True)
            for block in result.get("content_blocks", []):
                block["_source"] = name
            return result
        except Exception as e:
            logger.error(f"  Page {page_num}: {name} failed: {e}")
            if name == "gemini":
                self.tracker.record_gemini_call(success=False)
            else:
                self.tracker.record_gpt4o_call(success=False)
            return self._empty_result(page_num, f"{name} failed: {e}")

    def _apply_correction(
        self, page_data: Dict[str, Any], page_num: int
    ) -> Dict[str, Any]:
        """Apply Bangla text correction to the page's full text and individual blocks."""
        # Correct full_text_reading_order
        raw_text = page_data.get("full_text_reading_order", "")
        if raw_text and raw_text.strip():
            try:
                corrected = correction.correct_bangla_text(raw_text)
                page_data["full_text_reading_order"] = corrected
                page_data.setdefault("extraction_notes", []).append(
                    "Bangla correction applied to full_text_reading_order"
                )
                self.tracker.record_correction_call()
                logger.info(f"  Page {page_num}: Bangla correction applied")
            except Exception as e:
                logger.warning(f"  Page {page_num}: Correction failed: {e}")
                page_data.setdefault("extraction_notes", []).append(
                    f"Bangla correction failed: {str(e)}"
                )

        # Also correct individual low/medium-confidence blocks with Bangla text
        for block in page_data.get("content_blocks", []):
            conf = block.get("confidence", "high")
            block_text = block.get("text", "")
            if conf in ("low", "medium") and block_text:
                has_bangla = any(
                    config.BANGLA_UNICODE_START <= ord(ch) <= config.BANGLA_UNICODE_END
                    for ch in block_text
                )
                if has_bangla:
                    try:
                        block["text"] = correction.correct_bangla_text(block_text)
                        self.tracker.record_correction_call()
                    except Exception:
                        pass  # Keep original text if correction fails

        return page_data

    def _build_page_result(
        self, page_data: Dict[str, Any], page_img: PageImage, start_time: float
    ) -> PageResult:
        """Build a PageResult from raw page data."""
        content_blocks = []
        for block_data in page_data.get("content_blocks", []):
            cb = ContentBlock(
                block_id=block_data.get("block_id", 0),
                type=block_data.get("type", "paragraph"),
                position=block_data.get("position", "middle"),
                language=block_data.get("language", "mixed"),
                confidence=block_data.get("confidence", "high"),
                text=block_data.get("text", ""),
                is_handwritten=block_data.get("is_handwritten", False),
                _source=block_data.get("_source", ""),
                table=block_data.get("table"),
                fields=block_data.get("fields"),
            )
            content_blocks.append(cb)

        return PageResult(
            page_number=page_data.get("page_number", page_img.page_number),
            content_blocks=content_blocks,
            tables=page_data.get("tables", []),
            forms=page_data.get("forms", []),
            full_text_reading_order=page_data.get("full_text_reading_order", ""),
            extraction_notes=page_data.get("extraction_notes", []),
            processing_time_ms=(time.time() - start_time) * 1000,
            models_used=self._get_models_used(),
            image_path=page_img.image_path,
        )

    def _get_models_used(self) -> List[str]:
        """Get list of models actually used based on tracker."""
        models = []
        if self.tracker.gemini_calls > 0 or self.strategy in (
            "dual",
            "gemini_primary",
            "gemini_only",
        ):
            models.append(config.GEMINI_MODEL)
        if self.tracker.gpt4o_calls > 0 or self.strategy in (
            "dual",
            "gpt4o_primary",
            "gpt4o_only",
        ):
            models.append(config.OPENAI_MODEL)
        if not models:
            models.append(config.GEMINI_MODEL)
        return models

    @staticmethod
    def _empty_result(page_num: int, error_msg: str) -> Dict[str, Any]:
        """Return an empty result for a failed page."""
        return {
            "page_number": page_num,
            "content_blocks": [],
            "tables": [],
            "forms": [],
            "full_text_reading_order": "",
            "extraction_notes": [error_msg],
        }


# ── Convenience function ────────────────────────────────
def run_pipeline(
    pdf_path: str,
    output_dir: str = None,
    strategy: str = None,
    enable_correction: bool = True,
    dpi: int = None,
    progress_callback: Callable = None,
) -> DocumentResult:
    """
    Run the full PerfectOCR pipeline.

    Args:
        pdf_path: Path to PDF file
        output_dir: Output directory
        strategy: OCR strategy
        enable_correction: Enable Bangla correction
        dpi: Image DPI
        progress_callback: fn(step, detail, progress)

    Returns:
        DocumentResult
    """
    pipeline = PerfectOCRPipeline(
        pdf_path=pdf_path,
        output_dir=output_dir,
        strategy=strategy,
        enable_correction=enable_correction,
        dpi=dpi,
        progress_callback=progress_callback,
    )
    return pipeline.run()
