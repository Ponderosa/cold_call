"""Tests for printer rendering and raster data generation."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_printer.py: importing struct, PIL...")
import struct
from PIL import Image
_log.info("test_printer.py: importing cold_call.printer (triggers escpos + Pillow)...")
from cold_call.printer import (
    _render_text, _render_separator, _wrap_to_width, _compose_dispatch,
    _print_raster, PRINT_WIDTH, SIDE_MARGIN, FONT_REG, FONT_BOLD,
)
_log.info("test_printer.py: imports complete")


def test_render_text_dimensions():
    img = _render_text(["Hello"], size=24)
    assert img.width == PRINT_WIDTH
    assert img.height > 0
    assert img.mode == "1"


def test_render_text_multiline():
    one_line = _render_text(["A"], size=24)
    two_lines = _render_text(["A", "B"], size=24)
    assert two_lines.height > one_line.height


def test_render_text_padding():
    no_pad = _render_text(["X"], size=24)
    with_pad = _render_text(["X"], size=24, pad_top=20, pad_bottom=20)
    assert with_pad.height == no_pad.height + 40


def test_render_separator():
    img = _render_separator()
    assert img.width == PRINT_WIDTH
    assert img.mode == "1"


def test_wrap_to_width_fits_on_one_line():
    line = _wrap_to_width("Hello", FONT_BOLD, 40, 0, PRINT_WIDTH)
    assert line == ["Hello"]


def test_wrap_to_width_breaks_when_too_wide():
    lines = _wrap_to_width(
        "What is the meaning of life and everything else besides",
        FONT_BOLD, 40, 0, PRINT_WIDTH - 2 * SIDE_MARGIN,
    )
    assert len(lines) > 1
    assert " ".join(lines).split() == (
        "What is the meaning of life and everything else besides".split()
    )


def test_wrap_to_width_keeps_every_line_inside_the_column():
    """The whole point — no line may exceed the measure it was given."""
    from PIL import Image, ImageDraw, ImageFont

    max_width = PRINT_WIDTH - 2 * SIDE_MARGIN
    font = ImageFont.truetype(FONT_BOLD, 40)
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))

    for line in _wrap_to_width(
        "What is something you recently could not bring yourself to care about",
        FONT_BOLD, 40, 0, max_width,
    ):
        assert draw.textlength(line, font=font) <= max_width


def test_wrap_to_width_cannot_break_a_single_word():
    """An unbreakable word overflows rather than being silently truncated."""
    lines = _wrap_to_width("Supercalifragilisticexpialidocious", FONT_BOLD, 40,
                           0, PRINT_WIDTH - 2 * SIDE_MARGIN)
    assert lines == ["Supercalifragilisticexpialidocious"]


def test_wrap_to_width_balances_the_rag():
    """Greedy packs early lines full and leaves a stub; the rag is evened up.

    Greedy on this question gives widths 480/336/168/336 — a stub third line
    under two full ones. Balancing spreads the same words over the same
    number of lines.
    """
    from PIL import Image, ImageDraw, ImageFont

    text = "What group chats are you lurking in without participating?"
    max_width = PRINT_WIDTH - 2 * SIDE_MARGIN
    lines = _wrap_to_width(text, FONT_BOLD, 40, 0, max_width)

    font = ImageFont.truetype(FONT_BOLD, 40)
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))
    widths = [draw.textlength(line, font=font) for line in lines]

    assert " ".join(lines).split() == text.split(), "words were lost or reordered"
    assert all(w <= max_width for w in widths)
    # No line except the last may be less than half the widest.
    assert min(widths[:-1]) > max(widths) * 0.5


def test_compose_dispatch_returns_image():
    dispatch = _compose_dispatch("Test prompt?", theme="apathy", dispatch_num=1)
    assert isinstance(dispatch, Image.Image)
    assert dispatch.width == PRINT_WIDTH
    assert dispatch.height > 0
    assert dispatch.mode == "1"


def test_compose_dispatch_rotates():
    dispatch = _compose_dispatch("Test?", theme="apathy")
    rotated = dispatch.rotate(180)
    assert rotated.size == dispatch.size


def test_raster_bit_inversion():
    """Verify the PIL-to-ESC/POS bit inversion: PIL 0=black -> ESC/POS 1=black."""
    # All-white image (PIL mode 1: 255=white)
    white = Image.new("1", (8, 1), 1)
    raw = white.tobytes()
    inverted = bytes(b ^ 0xFF for b in raw)
    # All white -> all 0 bits in ESC/POS (no dots)
    assert inverted == b'\x00'

    # All-black image (PIL mode 1: 0=black)
    black = Image.new("1", (8, 1), 0)
    raw = black.tobytes()
    inverted = bytes(b ^ 0xFF for b in raw)
    # All black -> all 1 bits in ESC/POS (all dots)
    assert inverted == b'\xff'


def test_raster_data_size():
    """Raster data should be width_bytes * height."""
    img = Image.new("1", (PRINT_WIDTH, 100), 1)
    raw = img.tobytes()
    expected_bytes = (PRINT_WIDTH // 8) * 100
    assert len(raw) == expected_bytes


def test_print_raster_sends_correct_header():
    """Verify GS v 0 header format."""
    sent_data = bytearray()

    class FakePrinter:
        def _raw(self, data):
            sent_data.extend(data)

    img = Image.new("1", (PRINT_WIDTH, 10), 1)
    _print_raster(FakePrinter(), img)

    # Header: 1D 76 30 00 + width_bytes(LE) + height(LE)
    assert sent_data[:4] == b'\x1d\x76\x30\x00'
    width_bytes, height = struct.unpack('<HH', sent_data[4:8])
    assert width_bytes == PRINT_WIDTH // 8
    assert height == 10

    # Total data after header should be width_bytes * height
    raster = sent_data[8:]
    assert len(raster) == width_bytes * height


def _side_without_printer():
    from cold_call.hardware import Side
    return Side(label="A", card=1, card_id="Phone", printer_dev=None,
                usb_bus="fd500000.pcie", input_dev="/dev/input/event0")


def test_connection_unavailable_without_printer():
    from cold_call.printer import PrinterConnection
    pc = PrinterConnection(_side_without_printer())
    assert pc.available is False


def test_print_prompt_cuts_after_each_dispatch(monkeypatch, side_a):
    """Each dispatch is cut so it comes off as its own receipt.

    print_prompt swallows exceptions, so without this the cut could vanish
    or throw and every test would still pass.
    """
    from cold_call.printer import PrinterConnection

    calls = []

    class _Fake:
        def __init__(self, dev):
            pass

        def _raw(self, payload):
            calls.append("raw")

        def ln(self, count=1):
            calls.append("ln")

        def cut(self, *args, **kwargs):
            calls.append("cut")

        def close(self):
            calls.append("close")

    monkeypatch.setattr("cold_call.printer.File", _Fake)

    pc = PrinterConnection(side_a)
    pc.print_prompt("Do you feel seen?", theme="apathy", dispatch_num=1)

    assert "cut" in calls, "dispatch was not cut — receipts will run together"
    # order matters: cutting before the feed would slice through the receipt
    assert calls.index("cut") > calls.index("raw")
    assert calls.index("cut") > calls.index("ln")
    assert pc._printer is not None, "print_prompt failed and dropped the handle"


def test_print_calls_are_noops_without_printer():
    """Every public print path degrades quietly when no printer was paired."""
    from cold_call.printer import PrinterConnection
    pc = PrinterConnection(_side_without_printer())

    # None of these may raise — the session loop calls them unconditionally
    pc.print_prompt("Do you feel seen?", theme="apathy", dispatch_num=1)
    pc.print_status({"host": "test"})
    pc.buzzer_ring(cycles=1)
    pc.close()

    assert pc._printer is None
