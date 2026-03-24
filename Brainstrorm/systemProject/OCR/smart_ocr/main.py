"""
Smart OCR — CLI Entry Point
Run from command line:
  python -m smart_ocr.main <pdf_file>
  python -m smart_ocr.main <pdf_file> --mode gemini
  python -m smart_ocr.main <pdf_file> --no-paddle
"""

import sys
import argparse
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from smart_ocr.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Smart OCR — Production-grade PDF OCR (Bangla + English)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m smart_ocr.main document.pdf
  python -m smart_ocr.main document.pdf --mode smart
  python -m smart_ocr.main document.pdf --mode gemini
  python -m smart_ocr.main document.pdf --output-dir ./results
        """,
    )

    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "--mode",
        choices=["smart", "paddle", "gemini"],
        default="smart",
        help="Processing mode: smart (default), paddle (PaddleOCR only), gemini (old method)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: smart_ocr_output/)",
    )
    parser.add_argument(
        "--no-paddle",
        action="store_true",
        help="Disable PaddleOCR (use Gemini for all OCR pages)",
    )

    args = parser.parse_args()

    # Validate PDF
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    # Determine flags
    use_paddle = not args.no_paddle and args.mode != "gemini"
    force_gemini = args.mode == "gemini"

    # Progress callback for CLI
    def cli_progress(step, detail, progress):
        bar_len = 30
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r[{bar}] {progress:.0%} | {step}: {detail}", end="", flush=True)
        if progress >= 1.0:
            print()

    # Run pipeline
    print(f"\n{'='*60}")
    print(f"Smart OCR Pipeline")
    print(f"  PDF: {pdf_path}")
    print(f"  Mode: {args.mode}")
    print(f"  PaddleOCR: {'Yes' if use_paddle else 'No'}")
    print(f"{'='*60}\n")

    result = run_pipeline(
        pdf_path=str(pdf_path),
        output_dir=args.output_dir,
        progress_callback=cli_progress,
        use_paddle=use_paddle,
        force_gemini_all=force_gemini,
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Pages: {result.total_pages}")
    print(f"  Overall confidence: {result.overall_confidence:.1%}")
    print(
        f"  Gemini API calls: {result.gemini_usage_summary.get('total_api_calls', 0)}"
    )
    print(f"  Cache hits: {result.gemini_usage_summary.get('cache_hits', 0)}")
    print(f"  Processing time: {result.processing_time_ms:.0f}ms")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
