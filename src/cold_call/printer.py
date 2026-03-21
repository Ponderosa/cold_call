"""Printer controller for Cold Calls.

Renders prompt dispatches as images and prints them on MHT-80E thermal printers.
All text is rendered via Pillow for full typographic control.
"""

from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import TYPE_CHECKING

from escpos.printer import File
from escpos.image import EscposImage
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from cold_call.hardware import Side

PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
SEAL_PATH = ASSETS / "images" / "bureau_seal.png"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")


class PrinterConnection:
    """Persistent connection to one MHT-80E printer with auto-reconnect."""

    def __init__(self, side: Side):
        self.side = side
        self._printer: File | None = None

    def _connect(self) -> File:
        """Open and initialize the printer."""
        p = File(self.side.printer_dev)
        p._raw(b'\x1b\x40')  # ESC @ — initialize printer, clear buffer
        return p

    def _get(self) -> File:
        """Return an open printer, reconnecting if needed."""
        if self._printer is None:
            try:
                self._printer = self._connect()
            except (OSError, IOError) as e:
                print(f"  WARNING: Printer {self.side.label} "
                      f"({self.side.printer_dev}): {e}")
                raise
        return self._printer

    def _reconnect(self) -> File:
        """Force a reconnect."""
        self.close()
        return self._get()

    def buzzer_ring(self, cycles: int = 1):
        """Play a phone-ring pattern on the printer's buzzer."""
        try:
            p = self._get()
        except (OSError, IOError):
            return
        for i in range(cycles):
            p.buzzer(times=9, duration=1)
            time.sleep(1.5)
            p.buzzer(times=9, duration=1)
            if i < cycles - 1:
                time.sleep(3.0)

    def print_prompt(self, prompt: str, dispatch_num: int = 0):
        """Print a prompt dispatch."""
        try:
            p = self._get()
        except (OSError, IOError):
            try:
                p = self._reconnect()
            except (OSError, IOError):
                return

        dispatch = _compose_dispatch(prompt, dispatch_num)
        _print_raster_chunked(p, dispatch.rotate(180))

        p.ln(4)
        p.cut()

    def close(self):
        """Close the printer connection."""
        if self._printer is not None:
            try:
                self._printer.close()
            except Exception:
                pass
            self._printer = None


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


def _wrap_prompt(text: str, max_chars: int = 18) -> list[str]:
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
                                  pad_top=16, pad_bottom=4))
    sections.append(_render_text([f"{form_num}  |  Priority: Eventually"], size=18,
                                  pad_bottom=12))

    # Separator
    sections.append(_render_separator())

    # Question
    question_lines = _wrap_prompt(prompt)
    sections.append(Image.new("1", (PRINT_WIDTH, 8), 1))  # small gap
    for line in question_lines:
        sections.append(_render_text([line], font_path=FONT_BOLD, size=32,
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
    sections.append(_render_text(['"We\'ll get to it."'], size=18, pad_bottom=16))

    # Stitch all sections into one tall image
    total_h = sum(s.height for s in sections)
    composite = Image.new("1", (PRINT_WIDTH, total_h), 1)
    y = 0
    for section in sections:
        composite.paste(section, (0, y))
        y += section.height

    return composite


def _print_raster_chunked(p: File, img: Image.Image,
                           rows_per_chunk: int = 4, delay: float = 0.025):
    """Send a raster image in small chunks with delays for a dot-matrix feel.

    Manually sends the GS v 0 raster command in small row batches,
    creating a consistent mechanical printing rhythm on all printers.
    """
    ei = EscposImage(img)
    raster_data = ei.to_raster_format()

    width_bytes = img.width // 8
    height = img.height

    # GS v 0 m xL xH yL yH — raster bit image header
    header = b'\x1d\x76\x30\x00'
    header += struct.pack('<HH', width_bytes, height)
    p._raw(header)

    chunk_size = width_bytes * rows_per_chunk
    for i in range(0, len(raster_data), chunk_size):
        p._raw(raster_data[i:i + chunk_size])
        time.sleep(delay)
