#!/usr/bin/env python3
"""Bake department seals into the two print-ready sizes.

Source artwork lives in assets/seals/ at whatever size the designers export.
This writes assets/images/{theme}_seal.png (576px) and _seal_sm.png (288px),
both 1-bit. The small one is what actually prints — _compose_dispatch prefers
it and only falls back to the full size.

Only themes with a source file here are rebuilt; the rest of the seals in
assets/images/ predate this script and were baked by hand.

Usage:
    uv run python scripts/prep_seals.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "seals"
OUT_DIR = ROOT / "assets" / "images"

FULL = 576
SMALL = 288

# Seals are ring text and hairline rules. Downscaling to 288px thins both, so
# the threshold sits high to keep them from dropping out — same reasoning as
# the worksheets in prep_drawings.py, and more critical here because the small
# variant is the one that prints.
THRESHOLD = 200


def bake(src_path: Path, size: int) -> Image.Image:
    """Flatten, trim to the artwork, square up, scale, threshold to 1-bit."""
    img = Image.open(src_path)

    if "A" in img.getbands():
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
        img = flat

    img = img.convert("L")

    # Exports carry a lot of surrounding whitespace; the existing seals are
    # cropped tight, so match that or this one prints visibly smaller.
    ink = img.point(lambda v: 255 if v < 200 else 0)
    box = ink.getbbox()
    if box:
        img = img.crop(box)

    # Keep it round: pad the shorter axis rather than stretching.
    side = max(img.size)
    square = Image.new("L", (side, side), 255)
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))

    square = square.resize((size, size), Image.LANCZOS)
    return square.point(lambda v: 0 if v < THRESHOLD else 255).convert("1")


def main():
    sources = sorted(SRC_DIR.glob("*.png"))
    if not sources:
        print(f"No sources in {SRC_DIR.relative_to(ROOT)}/")
        return

    for src in sources:
        theme = src.stem
        for size, suffix in ((FULL, "_seal"), (SMALL, "_seal_sm")):
            out = OUT_DIR / f"{theme}{suffix}.png"
            bake(src, size).save(str(out))
            print(f"  {out.name}: {size}x{size}")


if __name__ == "__main__":
    main()
