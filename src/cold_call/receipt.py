"""Composition of the printed receipts.

Lays out what a dispatch and a status receipt contain, in reading order.
Knows nothing about devices — it returns images, and printer.py sends them.

This is where receipt structure grows. Typographic primitives belong in
typography.py; the rules governing both are in docs/DESIGN.md.
"""

from __future__ import annotations

import yaml
from PIL import Image

from cold_call.typography import (ASSETS, COLUMN, FONT_BOLD, FONT_REG, PRINT_WIDTH,
                                  SIDE_MARGIN, TOP_MARGIN, render_separator,
                                  render_text, stack, wrap_to_width)

# Load department metadata for seal/name lookup
_DEPTS_PATH = ASSETS / "departments.yaml"
_DEPARTMENTS: dict = {}
if _DEPTS_PATH.exists():
    with open(_DEPTS_PATH) as f:
        _DEPARTMENTS = yaml.safe_load(f).get("departments", {})


def _dept_info(theme: str) -> dict:
    """Get department metadata by theme key."""
    return _DEPARTMENTS.get(theme, {})


def compose_parts(prompt: str, theme: str = "apathy",
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
    # Two fields, two lines. Set in caps the combined line runs past the
    # column for three of the seven departments, and no size that fits is
    # worth reading — a form lists its fields separately anyway.
    form_lines = [
        f"{form_id or 'FORM'}-{dispatch_num:04d}".upper(),
        f"Priority: {priority}".upper(),
    ]
    sections.append(render_text(["APPROVED DIALOGUE"], font_path=FONT_BOLD,
                                  size=28, pad_top=16, pad_bottom=4, tracking=3))
    # Caps everywhere except the question and the instructions — see
    # docs/DESIGN.md. Only those two are read as sentences.
    sections.append(render_text(form_lines, size=18, line_spacing=2,
                                 pad_bottom=12, tracking=1))

    # Separator
    sections.append(render_separator())

    # Department identity
    name_lines = wrap_to_width(dept_name.upper(), FONT_BOLD, 20, 2,
                                PRINT_WIDTH - 2 * SIDE_MARGIN)
    sections.append(render_text(name_lines, font_path=FONT_BOLD,
                                  size=20, line_spacing=2, pad_top=12,
                                  pad_bottom=4, tracking=2))
    if tagline:
        sections.append(render_text([tagline.upper()], font_path=FONT_REG,
                                     size=16, pad_bottom=4, tracking=2))
    else:
        sections.append(Image.new("1", (PRINT_WIDTH, 4), 1))

    # Separator
    sections.append(render_separator())

    # Question
    # Wrapped by measured width, not character count — the face is
    # proportional, so counting characters gives a ragged, accidental measure.
    question_lines = wrap_to_width(prompt, FONT_BOLD, 40, 0,
                                    PRINT_WIDTH - 2 * SIDE_MARGIN)
    sections.append(Image.new("1", (PRINT_WIDTH, 24), 1))
    for line in question_lines:
        sections.append(render_text([line], font_path=FONT_BOLD, size=40,
                                      line_spacing=2, pad_top=2, pad_bottom=2))
    sections.append(Image.new("1", (PRINT_WIDTH, 24), 1))

    # Footer
    sections.append(render_separator())
    sections.append(render_text([
        "Please interview and record",
        "the response of the other party.",
    ], size=20, pad_top=12, pad_bottom=16, line_spacing=4))

    # Response worksheet — pre-baked by scripts/prep_drawings.py.
    # Not every department has one; those receipts just end at the footer.
    worksheet = []
    drawing_path = ASSETS / "images" / f"{theme}_drawing.png"
    if drawing_path.exists():
        # No rule opening this part. The instructions already close on one, and
        # the artwork carries its own — three rules in a row, two of them doing
        # the same job. Space divides it instead.
        worksheet.append(Image.open(drawing_path).convert("1"))
        worksheet.append(Image.new("1", (PRINT_WIDTH, 24), 1))

    parts = [stack(sections)]
    if worksheet:
        parts.append(stack(worksheet))
    return parts


def compose_dispatch(prompt: str, theme: str = "apathy",
                      dispatch_num: int = 0) -> Image.Image:
    """The whole dispatch as one image — previews, tests, and measurement."""
    return stack(compose_parts(prompt, theme=theme, dispatch_num=dispatch_num))


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


def compose_status(info: dict) -> Image.Image:
    """The boot receipt — what a station prints when it comes up.

    Lifted out of PrinterConnection, where the layout used to sit inside the
    method that opens the device. That is why this receipt was never brought
    into the design standard; it was hiding in the transport layer.
    """
    dept = _dept_info(info.get("theme", "")) if info.get("theme") else {}
    dept_name = dept.get("name", "Bureau of Ambient Belonging")

    sections = [
        render_text(
            wrap_to_width(dept_name.upper(), FONT_BOLD, 20, 2, COLUMN),
            font_path=FONT_BOLD, size=20, line_spacing=2,
            pad_top=16, pad_bottom=4, tracking=2,
        ),
        render_text(["SYSTEM STATUS REPORT"], size=18, pad_bottom=8, tracking=1),
        render_separator(),
    ]

    sections.append(render_text(
        [
            f"HOST:     {info.get('host', '?')}",
            f"IP:       {info.get('ip', '?')}",
            f"UPTIME:   {info.get('uptime', '?')}",
            f"STATION:  {info.get('station', '?')}",
            f"SIDE:     {info.get('side', '?')}",
            f"BUS:      {info.get('bus', '?')}",
            f"PHONE:    CARD {info.get('card', '?')}",
            f"PRINTER:  {info.get('printer_dev', '?')}",
        ],
        size=20, align="left", line_spacing=4, pad_top=8, pad_bottom=8,
    ))

    sections.append(render_separator())
    sections.append(render_text(["READY FOR CALLS."], font_path=FONT_BOLD,
                                 size=22, pad_top=8, pad_bottom=16, tracking=2))

    return stack(sections)
