#!/usr/bin/env python3
"""Build high-resolution WebP assets and a browser-ready manifest."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image


PAGE_PATTERN = re.compile(r"_页面_(\d+)_")
EXCLUDED_SOURCE_PAGES = {45}
EXPECTED_IMAGE_COUNT = 88


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def source_images(images_dir: Path) -> list[tuple[int, Path]]:
    images: list[tuple[int, Path]] = []
    for path in images_dir.glob("*.png"):
        match = PAGE_PATTERN.search(path.name)
        if match:
            source_page = int(match.group(1))
            if source_page not in EXCLUDED_SOURCE_PAGES:
                images.append((source_page, path))
    images.sort(key=lambda item: item[0])
    if len(images) != EXPECTED_IMAGE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_IMAGE_COUNT} PNG files, found {len(images)}")
    return images


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        if image.mode == "RGB":
            return image.copy()
        if "A" in image.mode:
            canvas = Image.new("RGB", image.size, "white")
            canvas.paste(image, mask=image.getchannel("A"))
            return canvas
        return image.convert("RGB")


def resize_for_web(image: Image.Image) -> Image.Image:
    resized = image.copy()
    if resized.width > 2400:
        target_height = round(resized.height * 2400 / resized.width)
        resized = resized.resize((2400, target_height), Image.Resampling.LANCZOS, reducing_gap=3.0)
    return resized


def write_manifest(path: Path, pages: list[dict[str, int | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(pages, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"window.PORTFOLIO_PAGES={payload};\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    images = source_images(args.images_dir)
    args.assets_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="portfolio-view-", dir=args.assets_dir.parent))
    pages: list[dict[str, int | str]] = []
    try:
        for display_page, (source_page, source_path) in enumerate(images, start=1):
            image = resize_for_web(open_rgb(source_path))
            filename = f"page-{display_page:02d}.webp"
            image.save(stage / filename, "WEBP", quality=88, method=6, optimize=True)
            pages.append(
                {
                    "display": display_page,
                    "source": source_page,
                    "file": filename,
                    "width": image.width,
                    "height": image.height,
                }
            )
        if args.assets_dir.exists():
            shutil.rmtree(args.assets_dir)
        shutil.move(str(stage), str(args.assets_dir))
        write_manifest(args.manifest, pages)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
    print(f"Built {len(pages)} high-resolution portfolio pages")


if __name__ == "__main__":
    main()
