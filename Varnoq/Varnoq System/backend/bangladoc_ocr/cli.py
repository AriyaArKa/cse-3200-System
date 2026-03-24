"""CLI entry point for BanglaDOC OCR."""

import argparse
import logging
from pathlib import Path

from bangladoc_ocr import config
from bangladoc_ocr.core.surya_engine import load as surya_load
from bangladoc_ocr.fallback.llm_fallback import get_service_status
from bangladoc_ocr.pipeline import process_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="BanglaDOC OCR CLI")
    parser.add_argument("pdfs", nargs="+", help="PDF files to process")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--domain", default="general", help="Domain tag for corpus metadata")
    args = parser.parse_args()

    config.refresh_config()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else getattr(logging, config.LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    surya_ready = surya_load() if config.SURYA_ENABLED else False
    services = get_service_status()

    print(f"Surya:  {'ready' if surya_ready else 'unavailable'}")
    print(
        "Ollama: "
        + (
            services.get("ollama_model")
            if services.get("ollama_available")
            else f"unavailable ({services.get('ollama_error') or 'unknown'})"
        )
    )
    print(f"Gemini: {'enabled' if config.GEMINI_ENABLED else 'disabled'}")

    for pdf in args.pdfs:
        pdf_path = Path(pdf)
        if not pdf_path.exists():
            print(f"ERROR: File not found: {pdf}")
            continue

        result = process_pdf(str(pdf_path), domain=args.domain)
        summary = result.to_dict()["document"]["processing_summary"]
        print(
            f"OK {result.source}: pages={result.total_pages} "
            f"conf={summary['overall_confidence']:.2%} "
            f"time={summary['processing_time_ms']:.0f}ms"
        )
        for page in result.pages:
            print(
                f"  page {page.page_number}: engine={page.extraction.engine} "
                f"conf={page.extraction.confidence_score:.3f}"
            )


if __name__ == "__main__":
    main()
