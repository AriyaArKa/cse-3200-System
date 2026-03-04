"""Test script to verify PerfectOCR v2.0 with Fast OCR optimization."""

from PerfectOCR import pipeline, fast_ocr, ocr_engines, config

print("=" * 60)
print("PerfectOCR v2.0 — System Check")
print("=" * 60)

print("\n✅ All modules imported successfully")
print(f"📦 Fast OCR module available: {fast_ocr.TESSERACT_AVAILABLE}")
print(f"🔧 Default strategy: {config.DEFAULT_STRATEGY}")
print(f"📐 Default DPI: {config.DPI}")
print(f"🔧 Correction model: {config.CORRECTION_MODEL}")

# Test tracker
tracker = ocr_engines.OCRUsageTracker()
print(f"✅ Tracker has tesseract field: {hasattr(tracker, 'tesseract_only_pages')}")

# Show optimization info
if fast_ocr.TESSERACT_AVAILABLE:
    print("\n⚡ FAST OCR OPTIMIZATION ENABLED")
    print("   Simple English text → Tesseract (no API calls)")
    print("   Complex/Bangla text → Gemini + GPT-4o fallback")
else:
    print("\n💡 Fast OCR optimization is NOT enabled")
    print("   Install pytesseract for faster processing of simple English docs:")
    print("   1. pip install pytesseract")
    print("   2. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")

print("\n" + "=" * 60)
print("System check complete. Ready to use!")
print("=" * 60)
