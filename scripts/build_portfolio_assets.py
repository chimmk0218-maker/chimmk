#!/usr/bin/env python3
"""Build optimized portfolio page images and hero thumbnails from exported PNGs."""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


PAGE_PATTERN = re.compile(r"_页面_(\d+)_")
HERO_PAGE_NUMBERS = [1, 3, 6, 9, 12, 15, 17, 20, 23, 27, 31, 35, 39, 43, 49, 56, 62, 68, 74, 80]
EXCLUDED_SOURCE_PAGES = {45}
EXPECTED_IMAGE_COUNT = 88


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--resume-image", type=Path, required=True)
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
    page_numbers = [number for number, _ in images]
    if len(set(page_numbers)) != len(page_numbers):
        raise RuntimeError("Duplicate source page numbers found")
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


def resize_portfolio_page(image: Image.Image) -> Image.Image:
    width, height = image.size
    bounds = (1600, 1200) if width / height >= 1.15 else (1200, 3000)
    resized = image.copy()
    resized.thumbnail(bounds, Image.Resampling.LANCZOS, reducing_gap=3.0)
    return resized


def save_webp(image: Image.Image, path: Path, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "WEBP", quality=quality, method=6, optimize=True)


def build_assets(images: list[tuple[int, Path]], stage: Path, resume_image: Path) -> None:
    pages_dir = stage / "portfolio-pages-2026"
    thumbs_dir = stage / "hero-thumbs-2026"
    pages_dir.mkdir(parents=True)
    thumbs_dir.mkdir(parents=True)

    source_by_display_page: dict[int, Path] = {}
    for display_page, (_, source) in enumerate(images, start=1):
        source_by_display_page[display_page] = source
        page = resize_portfolio_page(open_rgb(source))
        save_webp(page, pages_dir / f"page-{display_page:02d}.webp", quality=78)

    sprite = Image.new("RGB", (600, 680), "white")
    for index, display_page in enumerate(HERO_PAGE_NUMBERS, start=1):
        source = open_rgb(source_by_display_page[display_page])
        thumb = ImageOps.fit(
            source,
            (360, 203),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        save_webp(thumb, thumbs_dir / f"thumb-{index:02d}.webp", quality=72)
        tile = ImageOps.fit(
            source,
            (120, 170),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        col = (index - 1) % 5
        row = (index - 1) // 5
        sprite.paste(tile, (col * 120, row * 170))
    save_webp(sprite, stage / "hero-thumbs-2026.webp", quality=64)

    resume = open_rgb(resume_image)
    resume.thumbnail((1200, 1700), Image.Resampling.LANCZOS, reducing_gap=3.0)
    save_webp(resume, stage / "resume.webp", quality=82)


def replace_assets(stage: Path, assets_dir: Path) -> None:
    targets = [
        "portfolio-pages-2026",
        "hero-thumbs-2026",
        "hero-thumbs-2026.webp",
        "resume.webp",
    ]
    for name in targets:
        destination = assets_dir / name
        if destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists():
            destination.unlink()
        shutil.move(str(stage / name), str(destination))


def main() -> None:
    args = parse_args()
    images = source_images(args.images_dir)
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="portfolio-assets-", dir=args.assets_dir.parent))
    try:
        build_assets(images, stage, args.resume_image)
        replace_assets(stage, args.assets_dir)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    source_pages = [number for number, _ in images]
    print(f"Built {len(images)} portfolio pages from source pages {source_pages[0]}-{source_pages[-1]}")
    print(f"Missing exported source page numbers: {sorted(set(range(source_pages[0], source_pages[-1] + 1)) - set(source_pages))}")


if __name__ == "__main__":
    main()
