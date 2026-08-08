#!/usr/bin/env python3
"""Bake department response worksheets into print-ready 1-bit images.

Reads the source artwork from assets/drawings/ and writes thermal-ready
PNGs to assets/images/{theme}_drawing.png, sized to the 576px print width.

Same pattern as the pre-baked _sm seals: do the scaling and thresholding
once here, so the print path just pastes a bitmap.

Usage:
    uv run python scripts/prep_drawings.py
"""

from pathlib import Path

from PIL import Image

from cold_call.printer import PRINT_WIDTH

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "drawings"
OUT_DIR = ROOT / "assets" / "images"

# Cap height so one worksheet can't run away with the paper roll.
# 1000px ≈ 125mm at 203dpi.
MAX_HEIGHT = 1000

# Anything darker than this becomes black. Kept high so the hairline
# circles survive the downscale — a 128 threshold drops them entirely.
THRESHOLD = 190

# The six deployed departments (apathy is test-only and never ships).
THEMES = [
    "polite_indifference",
    "ambient_belonging",
    "acceptable_proximity",
    "minimal_engagement",
    "conditional_invitations",
    "deferred_enthusiasm",
]


def bake(src_path: Path) -> Image.Image:
    """Flatten, scale to fit the print area, and threshold to 1-bit."""
    img = Image.open(src_path)

    # Flatten transparency onto white — the sources are RGBA line art.
    if "A" in img.getbands():
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
        img = flat

    img = img.convert("L")

    scale = min(PRINT_WIDTH / img.width, MAX_HEIGHT / img.height)
    new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    img = img.resize(new_size, Image.LANCZOS)

    # Threshold rather than dither: dithered line art speckles on thermal.
    img = img.point(lambda v: 0 if v < THRESHOLD else 255).convert("1")

    # Center on the full print width so the print path can paste at x=0.
    if img.width < PRINT_WIDTH:
        canvas = Image.new("1", (PRINT_WIDTH, img.height), 1)
        canvas.paste(img, ((PRINT_WIDTH - img.width) // 2, 0))
        img = canvas

    return img


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for theme in THEMES:
        src = SRC_DIR / f"{theme}.png"
        if not src.exists():
            print(f"  SKIP {theme}: no source at {src.relative_to(ROOT)}")
            continue

        baked = bake(src)
        out = OUT_DIR / f"{theme}_drawing.png"
        baked.save(str(out))
        print(f"  {out.name}: {baked.width}x{baked.height}")

    print(f"\nBaked worksheets to {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
