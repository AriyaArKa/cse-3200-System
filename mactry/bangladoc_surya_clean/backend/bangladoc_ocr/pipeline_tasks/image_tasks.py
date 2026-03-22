"""Image-related helpers for page output and descriptions."""

import asyncio
from pathlib import Path

from bangladoc_ocr.core.image_describer import classify_heuristic, describe
from bangladoc_ocr.models import ImageResult


def describe_embedded_images(raw_images: list[dict], output_dir: Path, page_number: int) -> list[ImageResult]:
    results: list[ImageResult] = []
    for index, item in enumerate(raw_images, start=1):
        img_bytes = item["image_bytes"]
        width = item.get("width", 0)
        height = item.get("height", 0)
        image_type = classify_heuristic(width, height)

        ext = item.get("ext", "png")
        path = output_dir / f"p{page_number}_img{index}.{ext}"
        try:
            path.write_bytes(img_bytes)
        except Exception:
            pass

        description_text = ""
        try:
            loop = asyncio.new_event_loop()
            description_text = loop.run_until_complete(describe(img_bytes, image_type))
            loop.close()
        except Exception:
            description_text = ""

        results.append(
            ImageResult(
                image_id=index,
                type=image_type,
                detected_text="",
                description=description_text or f"{image_type} ({width}x{height}px)",
                confidence=0.80 if description_text else 0.50,
            )
        )

    return results


def save_page_image(img_bytes: bytes, output_dir: Path, page_number: int) -> str:
    path = output_dir / f"page_{page_number}.png"
    try:
        path.write_bytes(img_bytes)
        return str(path)
    except Exception:
        return ""
