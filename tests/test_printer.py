"""Tests for printer rendering and raster data generation."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_printer.py: importing struct, PIL...")
import struct
from PIL import Image
_log.info("test_printer.py: importing cold_call.printer (triggers escpos + Pillow)...")
from cold_call.printer import (
    _render_text, _render_separator, _wrap_prompt, _compose_dispatch,
    _print_raster, PRINT_WIDTH, FONT_REG, FONT_BOLD,
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


def test_wrap_prompt_short():
    assert _wrap_prompt("Hello") == ["Hello"]


def test_wrap_prompt_long():
    lines = _wrap_prompt("What is the meaning of life and everything else")
    assert all(len(line) <= 18 for line in lines)
    assert len(lines) > 1


def test_wrap_prompt_single_long_word():
    lines = _wrap_prompt("Supercalifragilisticexpialidocious")
    assert lines == ["Supercalifragilisticexpialidocious"]


def test_wrap_prompt_exact_fit():
    lines = _wrap_prompt("123456789012345678", max_chars=18)
    assert lines == ["123456789012345678"]


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
