"""
PerfectOCR — CLI Entry Point
Run from command line:
  python -m PerfectOCR.main <pdf_file>
  python -m PerfectOCR.main <pdf_file> --strategy dual
  python -m PerfectOCR.main <pdf_file> --strategy gemini_only
"""

import sys
import argparse
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from PerfectOCR.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="PerfectOCR — Dual-model OCR (GPT-4o + Gemini) for Bangla/English PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m PerfectOCR.main document.pdf
  python -m PerfectOCR.main document.pdf --strategy dual
  python -m PerfectOCR.main document.pdf --strategy gpt4o_only
  python -m PerfectOCR.main document.pdf --strategy gemini_only
  python -m PerfectOCR.main document.pdf --dpi 300 --no-correction
        """,
    )

    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "--strategy",
        choices=[
            "dual",
            "gpt4o_primary",
            "gemini_primary",
            "gpt4o_only",
            "gemini_only",
        ],
        default="dual",
        help="OCR strategy (default: dual)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Image DPI for conversion (default: 200)",
    )
    parser.add_argument(
        "--no-correction",
        action="store_true",
        help="Disable Bangla post-correction pass",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: perfect_ocr_output/)",
    )

    args = parser.parse_args()

    # Validate PDF
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    # Progress callback for CLI
    def cli_progress(step, detail, progress):
        bar_len = 30
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r[{bar}] {progress:.0%} | {step}: {detail}", end="", flush=True)
        if progress >= 1.0:
            print()

    # Run pipeline
    print(f"\n{'=' * 60}")
    print(f"PerfectOCR Pipeline")
    print(f"  PDF: {pdf_path}")
    print(f"  Strategy: {args.strategy}")
    print(f"  DPI: {args.dpi}")
    print(f"  Correction: {'Yes' if not args.no_correction else 'No'}")
    print(f"{'=' * 60}\n")

    result = run_pipeline(
        pdf_path=str(pdf_path),
        output_dir=args.output_dir,
        strategy=args.strategy,
        enable_correction=not args.no_correction,
        dpi=args.dpi,
        progress_callback=cli_progress,
    )

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results:")
    print(f"  Pages: {result.document.total_pages}")
    print(f"  Models: {', '.join(result.document.models_used)}")
    print(f"  Strategy: {result.strategy_used}")
    print(f"  Has tables: {result.document.has_tables}")
    print(f"  Has forms: {result.document.has_forms}")
    print(f"  Has handwriting: {result.document.has_handwriting}")
    print(f"  Processing time: {result.processing_time_ms:.0f}ms")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
