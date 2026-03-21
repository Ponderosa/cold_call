#!/usr/bin/env python3
"""Test script for MHT-80E thermal receipt printer.

Prints a Bureau of Apathy dispatch — a prompt card about recent apathy.
All text rendered as images using Courier Prime for full typographic control.

Usage:
    uv run python scripts/test_printer.py
"""

import time
from pathlib import Path

from escpos.printer import File
from PIL import Image, ImageDraw, ImageFont

PRINTER_DEV = "/dev/usb/lp0"
PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)
PAUSE = 0.6  # seconds between sections

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SEAL_PATH = ASSETS / "images" / "bureau_seal.png"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")


def render_text(lines, font_path=FONT_REG, size=24, align="center",
                line_spacing=8, pad_top=0, pad_bottom=0):
    """Render lines of text to a 1-bit image at PRINT_WIDTH."""
    font = ImageFont.truetype(font_path, size)
    # Use full font metrics for consistent line height (handles ascenders/descenders)
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
    """Render a separator line."""
    return render_text([char * count], font_path=font_path, size=size, pad_top=4, pad_bottom=4)


def render_gradient(steps=16, bar_height=20):
    """Render a greyscale test gradient, dithered to 1-bit."""
    step_width = PRINT_WIDTH // steps
    img = Image.new("L", (PRINT_WIDTH, bar_height + 30), 255)
    draw = ImageDraw.Draw(img)

    for i in range(steps):
        grey = int(255 * (1 - i / (steps - 1)))
        x0 = i * step_width
        draw.rectangle([x0, 0, x0 + step_width, bar_height], fill=grey)

    font = ImageFont.truetype(FONT_REG, 12)
    draw.text((2, bar_height + 2), "light", font=font, fill=0)
    bbox = draw.textbbox((0, 0), "dark", font=font)
    draw.text((PRINT_WIDTH - (bbox[2] - bbox[0]) - 2, bar_height + 2), "dark", font=font, fill=0)

    return img.convert("1")


def print_image(p, img):
    """Print a PIL image via escpos, rotated 180° so text reads correctly when pulled from printer."""
    p.image(img.rotate(180), impl="bitImageColumn")


FINE_PRINT = [
    "TERMS AND CONDITIONS OF APATHY",
    "",
    "Section 1. DEFINITIONS.",
    '"Apathy" shall refer to the general',
    "inability or disinclination to care",
    "about things one presumably should",
    "care about, as determined by society,",
    "one's mother, or the vague sense of",
    "guilt that follows you through the",
    "grocery store.",
    "",
    "Section 2. SCOPE.",
    "This dispatch covers all forms of",
    "apathy including but not limited to:",
    "(a) not voting on the group chat;",
    "(b) letting the laundry sit in the",
    "dryer for three days; (c) reading an",
    "alarming headline and scrolling past;",
    "(d) forgetting to have opinions about",
    "things your coworkers feel strongly",
    "about; (e) the quiet peace of not",
    "knowing who won the game last night.",
    "",
    "Section 3. OBLIGATIONS.",
    "The recipient is under no obligation",
    "to feel anything about this document.",
    "In fact, the Bureau encourages a",
    "posture of gentle indifference toward",
    "all official communications, including",
    "this one. If you have read this far,",
    "you may already be trying too hard.",
    "",
    "Section 4. DISCLAIMERS.",
    "The Bureau of Apathy makes no",
    "representations or warranties,",
    "express or implied, regarding the",
    "usefulness of caring. Past results",
    "do not guarantee future enthusiasm.",
    "Side effects of engagement may",
    "include: opinions, obligations, and",
    "calendar invites. The Bureau assumes",
    "no liability for feelings that may",
    "arise from participation in this or",
    "any Bureau-sponsored activity.",
    "",
    "Section 5. DURATION.",
    "This dispatch shall remain in effect",
    "until the recipient loses interest,",
    "which, statistically speaking, has",
    "already occurred.",
    "",
    "Section 6. AMENDMENTS.",
    "The Bureau reserves the right to",
    "amend these terms at any time, but",
    "probably won't get around to it.",
    "Proposed amendments must be submitted",
    "in triplicate on forms available at",
    "the Bureau's office, which is closed",
    "on days ending in 'y'.",
    "",
    "Section 7. GOVERNING LAW.",
    "This document is governed by the",
    "laws of inertia. Any disputes shall",
    "be resolved by whoever cares enough",
    "to show up, which historically has",
    "been no one.",
    "",
    "Section 8. CONTACT.",
    "For questions, concerns, or feedback,",
    "please do not contact us. We will not",
    "contact you either. This is the",
    "foundation of our relationship and we",
    "think it's working really well.",
    "",
    "Section 9. ACKNOWLEDGMENT.",
    "By continuing to hold this receipt,",
    "you acknowledge that you have read,",
    "or at least glanced at, or at minimum",
    "are physically proximate to, the",
    "terms set forth herein. Your presence",
    "is noted. Your enthusiasm is not",
    "required.",
    "",
    "Form 0.00 Rev. 0 | Bureau of Apathy",
    "\"We'll get to it.\"",
]


def print_dispatch(p: File):
    """Print a Bureau of Apathy prompt card.

    Printed bottom-up so the receipt reads correctly when pulled from the printer:
    fine print feeds out first (hidden), seal/header comes out last (visible on top).
    Each image is rotated 180° so text is right-side-up when the receipt hangs down.
    """

    # --- Fine print (prints first, ends up at the bottom of the receipt) ---
    # Print in reverse chunk order so the text reads top-to-bottom on the receipt
    chunk_size = 10
    chunks = []
    for i in range(0, len(FINE_PRINT), chunk_size):
        chunk = FINE_PRINT[i:i + chunk_size]
        chunk = [line if line else " " for line in chunk]
        chunks.append(chunk)
    for chunk in reversed(chunks):
        print_image(p, render_text(chunk, size=14, align="left", line_spacing=2,
                                   pad_top=0, pad_bottom=0))
        time.sleep(0.3)
    print_image(p, render_separator(char=".", count=40))
    time.sleep(PAUSE)

    # --- Greyscale test gradient ---
    print_image(p, render_gradient())
    print_image(p, render_text(["GREYSCALE TEST"], size=16, pad_top=12, pad_bottom=4))
    time.sleep(PAUSE)

    # --- Footer ---
    print_image(p, render_text(['"We\'ll get to it."'], size=18, pad_bottom=16))
    print_image(p, render_text(["BUREAU OF APATHY"], font_path=FONT_BOLD, size=22,
                               pad_top=12, pad_bottom=4))
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

    # --- Question — line by line with pauses (reversed) ---
    question_lines = [
        "What is something",
        "you recently could",
        "not bring yourself",
        "to care about,",
        "and did that feel",
        "like a problem or",
        "a relief?",
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
    print_image(p, render_text(["Form 0.00  |  Priority: Eventually"], size=18,
                               pad_bottom=12))
    print_image(p, render_text(["OFFICIAL DISPATCH"], font_path=FONT_BOLD, size=28,
                               pad_top=16, pad_bottom=4))
    time.sleep(PAUSE)

    # --- Seal logo (prints last, visible at top of receipt) ---
    seal = Image.open(SEAL_PATH).convert("1")
    if seal.width < PRINT_WIDTH:
        centered = Image.new("1", (PRINT_WIDTH, seal.height), 1)
        centered.paste(seal, ((PRINT_WIDTH - seal.width) // 2, 0))
        seal = centered
    print_image(p, seal)

    p.ln(4)
    p.cut()


def main():
    print(f"Opening printer at {PRINTER_DEV}...")
    p = File(PRINTER_DEV)

    print("Printing Bureau of Apathy dispatch...")
    print_dispatch(p)

    p.close()
    print("Done.")


if __name__ == "__main__":
    main()
