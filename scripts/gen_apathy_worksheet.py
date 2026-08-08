#!/usr/bin/env python3
"""Generate the Bureau of Apathy response worksheet.

The other six worksheets came from the designers. Apathy is our test-only
department, so this one is made up — deliberately the laziest of the set,
matching the tone of "We'll Get to It" and priority "Eventually".

Drawn at the same scale as the supplied artwork (~945px wide) so it bakes
through scripts/prep_drawings.py identically.

Usage:
    uv run python scripts/gen_apathy_worksheet.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "drawings" / "apathy.png"

# Matches the designers' source artwork dimensions and weight.
WIDTH = 945
HEIGHT = 760
MARGIN = 40
RULE = 7

SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

BOX = 190
BOX_Y = 380
CHOICES = ["SURE", "NOT REALLY", "PASS"]


def _tracked(draw, text, font, cx, y, tracking=6):
    """Draw letterspaced caps — the supplied worksheets are all tracked out."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=0)
        x += w + tracking


def main():
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    d = ImageDraw.Draw(img)
    label = ImageFont.truetype(SERIF_BOLD, 34)
    small = ImageFont.truetype(SERIF_BOLD, 30)
    centre = WIDTH / 2

    # A single rule to write on, in the style of the Minimal Engagement sheet.
    d.rectangle([MARGIN, 200, WIDTH - MARGIN, 200 + RULE], fill=0)
    _tracked(d, "IF YOU FEEL LIKE IT", label, centre, 224)

    # Three boxes to stamp, echoing the Conditional Invitations RSVP row.
    gap = (WIDTH - 2 * MARGIN - 3 * BOX) / 2
    for i, choice in enumerate(CHOICES):
        x = MARGIN + i * (BOX + gap)
        d.rectangle([x, BOX_Y, x + BOX, BOX_Y + BOX], outline=0, width=5)
        _tracked(d, choice, small, x + BOX / 2, BOX_Y + BOX + 22)

    img.convert("1").save(str(OUT))
    print(f"  {OUT.relative_to(ROOT)}: {img.width}x{img.height}")


if __name__ == "__main__":
    main()
