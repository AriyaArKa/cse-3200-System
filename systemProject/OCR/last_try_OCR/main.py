"""
CLI entry point for the Last-Try OCR system.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Disable OneDNN to avoid fused_conv2d errors on some CPUs
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("MKLDNN_CACHE_CAPACITY", "0")

# Ensure parent directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from last_try_OCR import config
from last_try_OCR.pipeline import process_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Last-Try OCR — Bangla + English PDF processing",
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        help="One or more PDF files to process",
    )
    parser.add_argument(
        "--no-mp",
        action="store_true",
        help="Disable multiprocessing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else getattr(logging, config.LOG_LEVEL)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    for pdf_path in args.pdf_paths:
        if not Path(pdf_path).exists():
            print(f"ERROR: File not found: {pdf_path}")
            continue
        result = process_pdf(pdf_path, use_multiprocessing=not args.no_mp)
        summary = result.to_dict()["document"]["processing_summary"]
        print(
            f"\n✓ {result.source}: "
            f"{result.total_pages} pages, "
            f"conf={summary['overall_confidence']:.2%}, "
            f"local={summary['pages_processed_locally']}, "
            f"api={summary['pages_sent_to_api']}, "
            f"time={summary['processing_time_ms']:.0f}ms"
        )


if __name__ == "__main__":
    main()
