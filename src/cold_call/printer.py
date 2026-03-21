"""Printer controller for Cold Calls.

Renders prompt dispatches as images and prints them on MHT-80E thermal printers.
All text is rendered via Pillow for full typographic control.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from escpos.printer import File
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from cold_call.hardware import Side

PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
SEAL_PATH = ASSETS / "images" / "bureau_seal.png"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")


def open_printer(side: Side, suppress_alarm: bool = False) -> File:
    """Open and initialize a printer for a side.

    Sends ESC @ to reset state. Optionally suppresses the paper-out alarm.
    """
    p = File(side.printer_dev)
    p._raw(b'\x1b\x40')  # ESC @ — initialize printer, clear buffer

    if suppress_alarm:
        # ESC c 4 n — enable/disable paper end sensor
        # n=0 disables the paper end signal, which suppresses the alarm buzzer
        p._raw(b'\x1b\x63\x04\x00')

    return p


def buzzer_ring(side: Side, cycles: int = 2):
    """Play a phone-ring pattern on the printer's buzzer.

    Two bursts per cycle with a pause between cycles, mimicking a phone ring.
    """
    p = File(side.printer_dev)
    p._raw(b'\x1b\x40')

    for i in range(cycles):
        p.buzzer(times=9, duration=1)  # burst 1
        time.sleep(1.5)
        p.buzzer(times=9, duration=1)  # burst 2
        if i < cycles - 1:
            time.sleep(3.0)  # pause between ring cycles

    p.close()


def _render_text(lines, font_path=FONT_REG, size=24, align="center",
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


def _render_separator(char="-", count=32):
    return _render_text([char * count], size=20, pad_top=4, pad_bottom=4)


def _wrap_prompt(text: str, max_chars: int = 24) -> list[str]:
    """Word-wrap a prompt string into lines that fit the bold print size."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _compose_dispatch(prompt: str, dispatch_num: int = 0) -> Image.Image:
    """Render an entire dispatch as one tall image (bottom to top).

    Returns a single 1-bit image ready to print. Building it as one image
    eliminates gaps between sections.
    """
    # Build sections top-to-bottom as they appear on the receipt
    # (we'll flip the whole thing at the end for bottom-up printing)
    sections = []

    # Seal
    seal = Image.open(SEAL_PATH).convert("1")
    if seal.width < PRINT_WIDTH:
        centered = Image.new("1", (PRINT_WIDTH, seal.height), 1)
        centered.paste(seal, ((PRINT_WIDTH - seal.width) // 2, 0))
        seal = centered
    sections.append(seal)

    # Header
    form_num = f"Form {dispatch_num:04d}" if dispatch_num else "Form 0.00"
    sections.append(_render_text(["OFFICIAL DISPATCH"], font_path=FONT_BOLD, size=28,
                                  pad_top=8, pad_bottom=4))
    sections.append(_render_text([f"{form_num}  |  Priority: Eventually"], size=18,
                                  pad_bottom=12))

    # Separator
    sections.append(_render_separator())

    # Question
    question_lines = _wrap_prompt(prompt)
    sections.append(Image.new("1", (PRINT_WIDTH, 8), 1))  # small gap
    for line in question_lines:
        sections.append(_render_text([line], font_path=FONT_BOLD, size=26,
                                      line_spacing=2, pad_top=2, pad_bottom=2))
    sections.append(Image.new("1", (PRINT_WIDTH, 8), 1))  # small gap

    # Separator
    sections.append(_render_separator())

    # Instructions
    sections.append(_render_text([
        "Please record your response",
        "using the provided stamps,",
        "stickers, and tape.",
    ], size=20, pad_top=12, line_spacing=4))

    sections.append(_render_text([
        "Do not use writing utensils.",
        "This is not that kind of form.",
    ], size=18, pad_top=8, pad_bottom=12, line_spacing=4))

    # Footer
    sections.append(_render_separator(char="_", count=30))
    sections.append(_render_text(["BUREAU OF APATHY"], font_path=FONT_BOLD, size=22,
                                  pad_top=12, pad_bottom=4))
    sections.append(_render_text(['"We\'ll get to it."'], size=18, pad_bottom=8))

    # Stitch all sections into one tall image
    total_h = sum(s.height for s in sections)
    composite = Image.new("1", (PRINT_WIDTH, total_h), 1)
    y = 0
    for section in sections:
        composite.paste(section, (0, y))
        y += section.height

    return composite


def print_prompt(side: Side, prompt: str, dispatch_num: int = 0,
                 suppress_alarm: bool = False):
    """Print a prompt dispatch to a side's printer.

    Renders the entire dispatch as one image and prints it in one operation
    for a smooth, gapless print. Image is rotated 180° so the receipt reads
    correctly when pulled from the printer (bottom-up print order).
    """
    p = open_printer(side, suppress_alarm=suppress_alarm)

    dispatch = _compose_dispatch(prompt, dispatch_num)
    p.image(dispatch.rotate(180), impl="bitImageRaster")

    p.ln(4)
    p.cut()
    p.close()
