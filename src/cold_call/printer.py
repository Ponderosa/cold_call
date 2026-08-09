"""Transport for the MHT-80E thermal printers.

Opens the device, sends raster, cuts, and degrades quietly when a printer is
missing. Layout lives in receipt.py; the drawing vocabulary in typography.py.
"""

from __future__ import annotations

import struct
import time
from typing import TYPE_CHECKING

from escpos.printer import File
from PIL import Image

from cold_call.receipt import compose_parts, compose_status

if TYPE_CHECKING:
    from cold_call.hardware import Side

FEED_LINES = 2     # ~8.5mm at 1/6" per line — part of the cut clearance

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
            parts = compose_parts(prompt, theme=theme,
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
            _print_raster(p, compose_status(info).rotate(180))
            p.ln(FEED_LINES)
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
