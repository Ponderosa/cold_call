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
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from cold_call.hardware import Side

import yaml

PRINT_WIDTH = 576  # 80mm at 203dpi (~72mm printable)
TOP_MARGIN = 64    # 8mm of leader, also part of the cut clearance
FEED_LINES = 2     # ~8.5mm at 1/6" per line — the rest of the clearance

# A 2400px dispatch (172,800 raster bytes in one GS v 0) desynced both
# printers mid-image: the firmware stopped consuming pixel data, printed the
# remainder as garbage text and swallowed the cut. The largest dispatch that
# printed cleanly was 169,200 bytes, so the real ceiling sits somewhere just
# above it. Banding the raster would avoid the limit but leaves visible gaps
# between bands, so instead we keep every dispatch comfortably under it.
MAX_RASTER_BYTES = 165_000

# Pause between the two raster commands of a dispatch, so the printer has time
# to drain rather than accumulate both halves.
RASTER_PAUSE = 0.4

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
FONT_REG = str(ASSETS / "fonts" / "CourierPrime-Regular.ttf")
FONT_BOLD = str(ASSETS / "fonts" / "CourierPrime-Bold.ttf")

# Load department metadata for seal/name lookup
_DEPTS_PATH = ASSETS / "departments.yaml"
_DEPARTMENTS: dict = {}
if _DEPTS_PATH.exists():
    with open(_DEPTS_PATH) as f:
        _DEPARTMENTS = yaml.safe_load(f).get("departments", {})


def _dept_info(theme: str) -> dict:
    """Get department metadata by theme key."""
    return _DEPARTMENTS.get(theme, {})


class PrinterConnection:
    """Persistent connection to one MHT-80E printer with auto-reconnect."""

    def __init__(self, side: Side):
        self.side = side
        self._printer: File | None = None
        self._warned = False

    @property
    def available(self) -> bool:
        """False when no printer was paired with this side at discovery."""
        return self.side.printer_dev is not None

    def _connect(self) -> File:
        """Open and initialize the printer."""
        if not self.available:
            raise OSError(f"No printer paired with side {self.side.label}")
        p = File(self.side.printer_dev)
        p._raw(b'\x1b\x40')  # ESC @ — initialize printer, clear buffer
        return p

    def _get(self) -> File:
        """Return an open printer, reconnecting if needed."""
        if self._printer is None:
            try:
                self._printer = self._connect()
            except (OSError, IOError) as e:
                # Warn once — _get is called on every print and every ring cycle
                if not self._warned:
                    print(f"  WARNING: Printer {self.side.label} "
                          f"({self.side.printer_dev or 'not connected'}): {e}")
                    self._warned = True
                raise
        self._warned = False
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
        try:
            for i in range(cycles):
                p.buzzer(times=9, duration=1)
                time.sleep(1.5)
                p.buzzer(times=9, duration=1)
                if i < cycles - 1:
                    time.sleep(3.0)
        except Exception:
            self.close()

    def print_prompt(self, prompt: str, theme: str = "apathy",
                     dispatch_num: int = 0):
        """Print a prompt dispatch. Fails gracefully if printer is dead."""
        try:
            p = self._get()
        except (OSError, IOError):
            try:
                p = self._reconnect()
            except (OSError, IOError):
                return

        try:
            parts = _compose_parts(prompt, theme=theme,
                                   dispatch_num=dispatch_num)
            # The image is rotated 180°, so the last part in reading order is
            # the first one off the head — print them back to front.
            for index, part in enumerate(reversed(parts)):
                if index:
                    # Let the printer drain before the next command. If the
                    # desync was a buffer filling up rather than a per-command
                    # ceiling, sending both halves back to back would hit the
                    # same wall as one big one.
                    time.sleep(RASTER_PAUSE)
                _print_raster(p, part.rotate(180))
            # TOP_MARGIN plus this feed is the white band above the seal, and
            # also the clearance the blade needs past the print head. Trimming
            # it further starts cutting into the seal.
            p.ln(FEED_LINES)
            p.cut()
        except Exception as e:
            print(f"  WARNING: Printer {self.side.label} failed mid-print: {e}")
            self.close()

    def print_status(self, info: dict):
        """Print a startup status receipt. Fails gracefully."""
        try:
            p = self._get()
        except (OSError, IOError):
            return

        try:
            sections = []

            theme = info.get("theme", "")
            dept = _dept_info(theme) if theme else {}
            dept_name = dept.get("name", "Bureau of Ambient Belonging")

            sections.append(_render_text(
                [dept_name.upper()],
                font_path=FONT_BOLD, size=20, pad_top=16, pad_bottom=4,
            ))
            sections.append(_render_text(
                ["System Status Report"],
                size=18, pad_bottom=8,
            ))
            sections.append(_render_separator())

            kv_lines = [
                f"Host:     {info.get('host', '?')}",
                f"IP:       {info.get('ip', '?')}",
                f"Uptime:   {info.get('uptime', '?')}",
                f"Station:  {info.get('station', '?')}",
                f"Side:     {info.get('side', '?')}",
                f"Bus:      {info.get('bus', '?')}",
                f"Phone:    card {info.get('card', '?')}",
                f"Printer:  {info.get('printer_dev', '?')}",
            ]
            sections.append(_render_text(
                kv_lines, size=20, align="left", line_spacing=4,
                pad_top=8, pad_bottom=8,
            ))

            sections.append(_render_separator())
            sections.append(_render_text(
                ["Ready for calls."],
                font_path=FONT_BOLD, size=22, pad_top=8, pad_bottom=16,
            ))

            total_h = sum(s.height for s in sections)
            composite = Image.new("1", (PRINT_WIDTH, total_h), 1)
            y = 0
            for section in sections:
                composite.paste(section, (0, y))
                y += section.height

            _print_raster(p, composite.rotate(180))
            p.ln(4)
            p.cut()
        except Exception as e:
            print(f"  WARNING: Printer {self.side.label} status print failed: {e}")
            self.close()

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


def _compose_parts(prompt: str, theme: str = "apathy",
                   dispatch_num: int = 0) -> list[Image.Image]:
    """Render a dispatch as the images that will be printed, in reading order.

    Returns [body] or [body, worksheet]. The split is deliberate: each part
    is sent as its own GS v 0, which keeps both well under the raster limit
    that desynced the printers, and the small feed the printer inserts
    between raster commands lands on the rule above the worksheet where it
    reads as intentional spacing rather than a seam.

    Uses department metadata from the theme for the seal, name, and tagline.
    """
    dept = _dept_info(theme)
    dept_name = dept.get("name", "Bureau of Apathy")
    tagline = dept.get("tagline", "")

    # Find seal image: prefer pre-baked small variant, fall back to full size
    seal_path = ASSETS / "images" / f"{theme}_seal_sm.png"
    if not seal_path.exists():
        seal_path = ASSETS / "images" / f"{theme}_seal.png"
    if not seal_path.exists():
        seal_path = ASSETS / "images" / "ambient_belonging_seal_sm.png"

    # Build sections top-to-bottom as they appear on the receipt
    sections = []

    # Top margin (8mm). This prints last — the image is rotated 180° — so it
    # doubles as clearance before the cut, on top of the ln(4) feed. It was
    # 30mm back when receipts came off as a continuous ribbon and the
    # whitespace was the only separation between them.
    sections.append(Image.new("1", (PRINT_WIDTH, TOP_MARGIN), 1))

    # Seal
    seal = Image.open(seal_path).convert("1")
    if seal.width < PRINT_WIDTH:
        centered = Image.new("1", (PRINT_WIDTH, seal.height), 1)
        centered.paste(seal, ((PRINT_WIDTH - seal.width) // 2, 0))
        seal = centered
    sections.append(seal)

    # Header
    form_id = dept.get("form", None)
    priority = dept.get("priority", "Eventually")
    if form_id:
        form_line = f"{form_id}-{dispatch_num:04d}  |  Priority: {priority}"
    else:
        form_line = f"Form {dispatch_num:04d}  |  Priority: {priority}"
    sections.append(_render_text(["APPROVED DIALOGUE"], font_path=FONT_BOLD, size=28,
                                  pad_top=16, pad_bottom=4))
    sections.append(_render_text([form_line], size=18, pad_bottom=12))

    # Separator
    sections.append(_render_separator())

    # Department identity
    sections.append(_render_text([dept_name.upper()], font_path=FONT_BOLD, size=20,
                                  pad_top=12, pad_bottom=4))
    if tagline:
        sections.append(_render_text([f'"{tagline}"'], size=16, pad_bottom=4))
    else:
        sections.append(Image.new("1", (PRINT_WIDTH, 4), 1))

    # Separator
    sections.append(_render_separator())

    # Question
    question_lines = _wrap_prompt(prompt, max_chars=14)
    sections.append(Image.new("1", (PRINT_WIDTH, 24), 1))
    for line in question_lines:
        sections.append(_render_text([line], font_path=FONT_BOLD, size=40,
                                      line_spacing=2, pad_top=2, pad_bottom=2))
    sections.append(Image.new("1", (PRINT_WIDTH, 24), 1))

    # Footer
    sections.append(_render_separator(char="_", count=30))
    sections.append(_render_text([
        "Please interview and record",
        "the response of the other party.",
    ], size=20, pad_top=12, pad_bottom=16, line_spacing=4))

    # Response worksheet — pre-baked by scripts/prep_drawings.py.
    # Not every department has one; those receipts just end at the footer.
    worksheet = []
    drawing_path = ASSETS / "images" / f"{theme}_drawing.png"
    if drawing_path.exists():
        worksheet.append(_render_separator(char="_", count=30))
        worksheet.append(Image.open(drawing_path).convert("1"))
        worksheet.append(Image.new("1", (PRINT_WIDTH, 24), 1))

    parts = [_stack(sections)]
    if worksheet:
        parts.append(_stack(worksheet))
    return parts


def _stack(sections) -> Image.Image:
    """Paste sections into one tall image, top to bottom."""
    composite = Image.new("1", (PRINT_WIDTH, sum(s.height for s in sections)), 1)
    y = 0
    for section in sections:
        composite.paste(section, (0, y))
        y += section.height
    return composite


def _compose_dispatch(prompt: str, theme: str = "apathy",
                      dispatch_num: int = 0) -> Image.Image:
    """The whole dispatch as one image — previews, tests, and measurement."""
    return _stack(_compose_parts(prompt, theme=theme, dispatch_num=dispatch_num))


# Bytes the MHT-80E firmware treats as the start of a command. Taken from the
# firmware image itself (XOR 0xa3, ARM Thumb): the parser at 0x9810 rebases the
# byte by 0x14 and runs a `tbb` jump table over 0x14-0x1a, then compares ESC,
# FS, GS, RS and US explicitly. DLE is handled by the separate real-time
# command path. Anything in this range can put the printer into IAP
# firmware-update mode — we have already lost one printer that way.
COMMAND_BYTES = (0x10,) + tuple(range(0x14, 0x20))

# Escape targets must not themselves be dispatched. Flipping bit 5 lands every
# command byte in 0x30-0x3f, which the parser rejects outright, and still costs
# a single pixel. The earlier substitutions flipped bit 0 or 1 instead, which
# mapped ESC->SUB, FS->RS and GS->US — all three of them live commands — so the
# sanitizer was manufacturing the very bytes it existed to remove.
_ESCAPE_BIT = 0x20


def _sanitize_raster(data: bytes) -> bytes:
    """Remove ESC/POS command-initiator bytes from raster data.

    The MHT-80E firmware erroneously scans raster pixel data for command
    sequences. Each dangerous byte is replaced by a single bit flip, which
    moves one pixel and is visually imperceptible.
    """
    table = bytearray(range(256))
    for b in COMMAND_BYTES:
        table[b] = b ^ _ESCAPE_BIT
    return data.translate(bytes(table))


def _print_raster(p: File, img: Image.Image):
    """Send a raster image as a single GS v 0 command.

    Builds raster data directly from the 1-bit PIL image, bypassing
    EscposImage (which needlessly round-trips through RGBA/L/invert).
    PIL mode "1": 0=black, 1=white. ESC/POS raster: 1=black, 0=white.
    So we invert the packed bytes, then sanitize to remove any byte values
    the printer firmware might misinterpret as commands.
    """
    if img.mode != "1":
        img = img.convert("1")
    raw = img.tobytes()
    raster_data = bytes(b ^ 0xFF for b in raw)
    raster_data = _sanitize_raster(raster_data)
    width_bytes = img.width // 8
    height = img.height

    header = b'\x1d\x76\x30\x00'
    header += struct.pack('<HH', width_bytes, height)
    p._raw(header + raster_data)
