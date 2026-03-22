"""Helper functions shared across pipeline tasks."""

import hashlib
from pathlib import Path

from bangladoc_ocr.models import ContentBlock, PageResult
from bangladoc_ocr.nlp.bangla_corrector import correct_bangla_text
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio, strip_devanagari_dominant_lines


def text_to_blocks(text: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    for i, paragraph in enumerate(paragraphs, start=1):
        ratio = bangla_char_ratio(paragraph)
        language = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
        blocks.append(
            ContentBlock(
                block_id=i,
                type="paragraph",
                language=language,
                text=paragraph,
                confidence=0.90,
            )
        )
    return blocks


def apply_corrections(blocks: list[ContentBlock], source: str) -> tuple[list[ContentBlock], bool]:
    changed = False
    for block in blocks:
        if block.language in ("bn", "mixed") and block.text:
            new_text, correction_log = correct_bangla_text(block.text, source=source)
            new_text, script_cleaned = strip_devanagari_dominant_lines(new_text)
            if correction_log.get("corrections"):
                changed = True
            if script_cleaned:
                changed = True
            block.text = new_text
    return blocks, changed


def detect_languages(pages: list[PageResult]) -> list[str]:
    languages = set()
    for page in pages:
        if any(block.language in ("bn", "mixed") for block in page.content_blocks):
            languages.add("bn")
        if any(block.language in ("en", "mixed") for block in page.content_blocks):
            languages.add("en")
    return sorted(languages) or ["unknown"]


def build_doc_id(pdf_path: Path) -> str:
    stem = pdf_path.stem
    digest = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}"
