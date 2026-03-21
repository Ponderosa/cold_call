#!/usr/bin/env python3
"""Test script for MHT-80E thermal receipt printer.

Prints an Office of Acceptable Proximity dispatch.
All text rendered as images using Courier Prime for full typographic control.

Usage:
    uv run python scripts/test_printer_proximity.py [A|B]
"""

import sys
import time
from pathlib import Path

from escpos.printer import File
from PIL import Image, ImageDraw, ImageFont

from cold_call.hardware import discover_sides

PRINT_WIDTH = 576
PAUSE = 0.6

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SEAL_PATH = ASSETS / "images" / "proximity_seal.png"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")


def render_text(lines, font_path=FONT_REG, size=24, align="center",
                line_spacing=8, pad_top=0, pad_bottom=0):
    """Render lines of text to a 1-bit image at PRINT_WIDTH."""
    font = ImageFont.truetype(font_path, size)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent

    total_h = line_h * len(lines) + line_spacing * (len(lines) - 1) + pad_top + pad_bottom
    img = Image.new("1", (PRINT_WIDTH, total_h), 1)
    draw = ImageDraw.Draw(img)

    y = pad_top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align == "center":
            x = (PRINT_WIDTH - tw) // 2
        elif align == "right":
            x = PRINT_WIDTH - tw
        else:
            x = 0
        draw.text((x, y), line, font=font, fill=0)
        y += line_h + line_spacing

    return img


def render_separator(char="-", count=32, font_path=FONT_REG, size=20):
    return render_text([char * count], font_path=font_path, size=size, pad_top=4, pad_bottom=4)


def print_image(p, img):
    """Print a PIL image via escpos, rotated 180° for upside-down feed."""
    p.image(img.rotate(180), impl="bitImageColumn")


FINE_PRINT = [
    "GUIDELINES FOR ACCEPTABLE PROXIMITY",
    "",
    "Section 1. PURPOSE.",
    "The Office of Acceptable Proximity",
    "was established to address the",
    "growing crisis of people standing",
    "too close to other people. Our",
    "mandate is clear: maintain the",
    "buffer zone.",
    "",
    "Section 2. APPROVED DISTANCES.",
    "(a) Strangers: one full outstretched",
    "arm, minimum. Two arms preferred.",
    "(b) Acquaintances: close enough to",
    "wave, far enough to pretend you",
    "didn't see them. (c) Close friends:",
    "variable, but never close enough to",
    "smell what they had for lunch.",
    "(d) Escalators: one step apart.",
    "This is non-negotiable.",
    "",
    "Section 3. PROHIBITED ZONES.",
    "The following proximity violations",
    "are subject to formal review:",
    "(a) reading over someone's shoulder;",
    "(b) breathing audibly near someone's",
    "neck; (c) choosing the adjacent",
    "urinal when others are available;",
    "(d) standing directly behind someone",
    "in an otherwise empty room; (e) the",
    "thing where someone matches your",
    "walking pace on the sidewalk.",
    "",
    "Section 4. THE PHONE EXCEPTION.",
    "Two strangers holding telephones",
    "connected to the same art",
    "installation are hereby granted",
    "a temporary proximity waiver.",
    "The Office acknowledges this is",
    "unusual. Please direct complaints",
    "to the Bureau of Ambient Belonging.",
    "",
    "Section 5. ENFORCEMENT.",
    "The Office does not employ",
    "enforcement officers. Compliance",
    "is maintained through the universal",
    "human experience of discomfort.",
    "If someone is too close, you will",
    "know. They will also know. Everyone",
    "knows. And yet.",
    "",
    "Section 6. APPEALS.",
    "If you believe you have been",
    "unfairly deemed 'too close,' you",
    "may submit a formal appeal by",
    "taking one step backward. Appeal",
    "granted. See how easy that was.",
    "",
    "Section 7. EXCEPTIONS.",
    "Concerts, subways, and elevators",
    "are recognized as proximity",
    "lawless zones. The Office has no",
    "jurisdiction there. You are on",
    "your own. Godspeed.",
    "",
    "Section 8. CLOSING REMARKS.",
    "Personal space is a renewable",
    "resource, but only if people",
    "stop taking yours. Be the",
    "distance you wish to see in",
    "the world.",
    "",
    "Form P-1.5m | Rev. 0",
    "Office of Acceptable Proximity",
    '"Not too close."',
]


def print_dispatch(p: File):
    """Print an Office of Acceptable Proximity dispatch (bottom-up)."""

    # --- Fine print first (bottom of receipt) ---
    chunk_size = 10
    chunks = []
    for i in range(0, len(FINE_PRINT), chunk_size):
        chunk = FINE_PRINT[i:i + chunk_size]
        chunk = [line if line else " " for line in chunk]
        chunks.append(chunk)
    for chunk in reversed(chunks):
        print_image(p, render_text(chunk, size=14, align="left", line_spacing=2))
        time.sleep(0.3)
    print_image(p, render_separator(char=".", count=40))
    time.sleep(PAUSE)

    # --- Footer ---
    print_image(p, render_text(['"Not too close."'], size=18, pad_bottom=16))
    print_image(p, render_text(["OFFICE OF ACCEPTABLE PROXIMITY"],
                               font_path=FONT_BOLD, size=18, pad_top=12, pad_bottom=4))
    print_image(p, render_separator(char="_", count=30))
    time.sleep(PAUSE)

    # --- Instructions ---
    print_image(p, render_text([
        "Do not use writing utensils.",
        "This is not that kind of form.",
    ], size=18, pad_top=8, pad_bottom=12, line_spacing=4))
    time.sleep(PAUSE)

    print_image(p, render_text([
        "Please record your response",
        "using the provided stamps,",
        "stickers, and tape.",
    ], size=20, pad_top=12, line_spacing=4))
    time.sleep(PAUSE)

    # --- Separator ---
    print_image(p, render_separator())
    time.sleep(PAUSE)

    # --- Question (reversed) ---
    question_lines = [
        "When was the last",
        "time a stranger",
        "stood too close",
        "to you, and what",
        "did you do about",
        "it — if anything?",
    ]
    p.ln()
    for line in reversed(question_lines):
        print_image(p, render_text([line], font_path=FONT_BOLD, size=32,
                                   line_spacing=2, pad_top=2, pad_bottom=2))
        time.sleep(PAUSE)
    time.sleep(PAUSE)

    # --- Separator ---
    print_image(p, render_separator())
    time.sleep(PAUSE)

    # --- Subtitle ---
    print_image(p, render_text(["Form P-1.5m  |  Clearance: Arm's Length"], size=16,
                               pad_bottom=12))
    print_image(p, render_text(["PROXIMITY ADVISORY"], font_path=FONT_BOLD, size=28,
                               pad_top=16, pad_bottom=4))
    time.sleep(PAUSE)

    # --- Seal (prints last, top of receipt) ---
    seal = Image.open(SEAL_PATH).convert("1")
    if seal.width < PRINT_WIDTH:
        centered = Image.new("1", (PRINT_WIDTH, seal.height), 1)
        centered.paste(seal, ((PRINT_WIDTH - seal.width) // 2, 0))
        seal = centered
    print_image(p, seal)

    p.ln(4)
    p.cut()


def main():
    sides = discover_sides()

    which = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
    side = next((s for s in sides if s.label == which), None)
    if side is None:
        sys.exit(f"ERROR: Side '{which}' not found. Available: {[s.label for s in sides]}")

    print(f"Side {side.label}: printer {side.printer_dev}")
    p = File(side.printer_dev)

    print("Printing Office of Acceptable Proximity dispatch...")
    print_dispatch(p)

    p.close()
    print("Done.")


if __name__ == "__main__":
    main()
