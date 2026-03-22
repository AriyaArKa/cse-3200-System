"""Text parsing helpers for OCR LLM output."""

import json
from typing import List, Optional

from bangladoc_ocr.models import ContentBlock
from bangladoc_ocr.nlp.unicode_validator import bangla_char_ratio


def text_to_blocks(text: str, offset: int = 1) -> List[ContentBlock]:
    if not text:
        return []

    parsed = try_parse_json(text, offset)
    if parsed:
        return parsed

    blocks: List[ContentBlock] = []
    block_id = offset
    current: List[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                joined = "\n".join(current)
                ratio = bangla_char_ratio(joined)
                lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
                blocks.append(
                    ContentBlock(
                        block_id=block_id,
                        type="paragraph",
                        language=lang,
                        text=joined,
                        confidence=0.9,
                    )
                )
                block_id += 1
                current = []
            continue
        current.append(stripped)

    if current:
        joined = "\n".join(current)
        ratio = bangla_char_ratio(joined)
        lang = "bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en")
        blocks.append(
            ContentBlock(
                block_id=block_id,
                type="paragraph",
                language=lang,
                text=joined,
                confidence=0.9,
            )
        )

    return blocks


def try_parse_json(text: str, offset: int) -> Optional[List[ContentBlock]]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:] if lines and lines[0].startswith("```") else lines).rstrip("`").strip()

    try:
        data = json.loads(clean)
    except Exception:
        return None

    blocks_data = []
    if isinstance(data, dict):
        for key in ("content_blocks", "blocks", "content", "results"):
            if isinstance(data.get(key), list):
                blocks_data = data[key]
                break
    elif isinstance(data, list):
        blocks_data = data

    if not blocks_data:
        return None

    blocks: List[ContentBlock] = []
    for i, item in enumerate(blocks_data):
        if not isinstance(item, dict):
            continue
        text_value = (item.get("text") or "").strip()
        if not text_value:
            continue
        ratio = bangla_char_ratio(text_value)
        lang = item.get("language") or ("bn" if ratio > 0.5 else ("mixed" if ratio > 0.1 else "en"))
        blocks.append(
            ContentBlock(
                block_id=offset + i,
                type=item.get("type", "paragraph"),
                language=lang,
                text=text_value,
                confidence=float(item.get("confidence", 0.9)),
                is_handwritten=bool(item.get("is_handwritten", False)),
            )
        )

    return blocks or None
