"""Exhaustive raster-safety sweep over the whole prompt corpus.

The MHT-80E firmware scans raster pixel data for ESC/POS command sequences.
A command-initiator byte surviving into the pixel stream can put the printer
into IAP firmware-update mode — we have already lost one printer this way.
`_sanitize_raster` exists to prevent it; this is what proves it holds for
every dispatch we can actually print.

Runs offline against the real print path — no printer, no paper. For a
physical burn-in, see scripts/soak_printer.py.
"""

from __future__ import annotations

from collections import Counter

import pytest

from cold_call.hardware import Side
from cold_call.printer import (MAX_RASTER_BYTES, PrinterConnection, _print_raster,
                               _sanitize_raster)
from cold_call.receipt import compose_dispatch, compose_parts
from cold_call.prompts import load_prompts

# Bytes the firmware treats as the start of a command, listed independently of
# the printer module so this file acts as the specification rather than echoing
# the implementation. Read out of the firmware image (XOR 0xa3, ARM Thumb): the
# parser at 0x9810 runs a `tbb` jump table over 0x14-0x1a and compares ESC, FS,
# GS, RS and US explicitly, with DLE handled on the real-time path.
COMMAND_BYTES = {
    0x10: "DLE",
    0x14: "DC4",
    0x15: "NAK",
    0x16: "SYN",
    0x17: "ETB",
    0x18: "CAN",
    0x19: "EM",
    0x1a: "SUB",
    0x1b: "ESC",
    0x1c: "FS",
    0x1d: "GS",
    0x1e: "RS",
    0x1f: "US",
}

DEPARTMENTS = [
    "apathy",
    "polite_indifference",
    "ambient_belonging",
    "acceptable_proximity",
    "minimal_engagement",
    "conditional_invitations",
    "deferred_enthusiasm",
]

# GS v 0 m xL xH yL yH — everything after this is pixel data.
RASTER_HEADER = b"\x1d\x76\x30\x00"
HEADER_LEN = 8

# The documented brick: 0x13a44 reads three stream bytes and jumps to the IAP
# entry — magic 0x12345678, then NVIC_SystemReset — when they are CAN, EM, 0x01.
# The printer reboots into its bootloader and stops being a printer.
# Blocked today because 0x18 and 0x19 are both sanitized; asserted directly so
# that trimming the byte list fails here and not at a museum.
BRICK_SEQUENCE = b"\x18\x19\x01"


class _CapturePrinter:
    """Stands in for escpos File, keeping the bytes _print_raster emits."""

    def __init__(self):
        self.data = b""

    def _raw(self, payload):
        self.data += payload


def _raster_payload(prompt: str, theme: str) -> bytes:
    """Return the pixel bytes for a dispatch, exactly as sent to the printer."""
    dispatch = compose_dispatch(prompt, theme=theme, dispatch_num=1)
    cap = _CapturePrinter()
    _print_raster(cap, dispatch.rotate(180))
    return cap.data[HEADER_LEN:]


def _all_dispatches():
    """Every (theme, prompt) pair the installation can print."""
    for theme in DEPARTMENTS:
        for prompt in load_prompts(theme):
            yield theme, prompt


def test_corpus_is_fully_loaded():
    """Guard the sweep itself — an empty corpus would pass every test below.

    Deliberately count-agnostic: the prompt lists get rewritten per station,
    so pinning a total would just mean editing this test every time. What
    matters is that no department silently contributes nothing.
    """
    pairs = list(_all_dispatches())
    assert pairs, "no prompts loaded at all — the sweep below would be vacuous"

    counts = Counter(theme for theme, _ in pairs)
    empty = [theme for theme in DEPARTMENTS if not counts[theme]]
    assert not empty, f"departments with no prompts: {empty}"


@pytest.mark.parametrize("theme,prompt", _all_dispatches())
def test_no_command_bytes_in_raster(theme, prompt):
    """No dispatch may emit a command-initiator byte in its pixel data.

    Also asserts the brick sequence directly. Both checks share one render
    because composing 175 dispatches is what makes this sweep slow.
    """
    payload = _raster_payload(prompt, theme)

    found = {b: payload.count(b) for b in COMMAND_BYTES if b in payload}
    assert not found, (
        f"{theme}: raster contains command bytes "
        + ", ".join(f"0x{b:02x} ({COMMAND_BYTES[b]}) x{n}" for b, n in found.items())
        + f" — prompt: {prompt!r}"
    )

    assert BRICK_SEQUENCE not in payload, (
        f"{theme}: raster contains the IAP brick sequence 18 19 01 — "
        f"prompt: {prompt!r}"
    )


class _CaptureFile:
    """Stands in for the escpos File so print_status runs without hardware."""

    last = None

    def __init__(self, dev):
        self.dev = dev
        self.writes = []
        _CaptureFile.last = self

    def _raw(self, payload):
        self.writes.append(payload)

    def ln(self, count=1):
        pass

    def cut(self):
        pass

    def close(self):
        pass


def _status_payload(monkeypatch, info) -> bytes:
    """Pixel bytes of a status receipt, taken from the real print path."""
    monkeypatch.setattr("cold_call.printer.File", _CaptureFile)
    side = Side(label="A", card=1, card_id="Phone", printer_dev="/dev/null",
                usb_bus="test", input_dev=None)

    PrinterConnection(side).print_status(info)

    raster = [w for w in _CaptureFile.last.writes if w.startswith(RASTER_HEADER)]
    # print_status swallows exceptions, so an empty capture means it failed
    # silently rather than that the receipt was clean.
    assert len(raster) == 1, f"expected one raster write, captured {len(raster)}"
    return raster[0][HEADER_LEN:]


# The status receipt prints on every boot of every station, unattended, so it
# reaches paper without anyone choosing to trigger it. Field values vary by
# host, so vary them here too.
STATUS_INFOS = [
    pytest.param({"theme": "ambient_belonging", "host": "coldcall-1",
                  "ip": "192.168.1.40", "uptime": "0:01", "station": "station1",
                  "side": "A", "bus": "fd500000.pcie", "card": 1,
                  "printer_dev": "/dev/usb/lp0"}, id="typical"),
    pytest.param({"theme": "deferred_enthusiasm", "host": "coldcall-station-3",
                  "ip": "10.0.0.255", "uptime": "128:59", "station": "station3",
                  "side": "B", "bus": "fe980000.usb", "card": 12,
                  "printer_dev": "/dev/usb/lp1"}, id="long-fields"),
    pytest.param({}, id="empty-degraded"),
]


@pytest.mark.parametrize("info", STATUS_INFOS)
def test_status_receipt_has_no_command_bytes(monkeypatch, info):
    """The boot receipt goes through the same raster path and must be clean."""
    payload = _status_payload(monkeypatch, info)

    found = {b: payload.count(b) for b in COMMAND_BYTES if b in payload}
    assert not found, (
        "status receipt contains command bytes "
        + ", ".join(f"0x{b:02x} ({COMMAND_BYTES[b]}) x{n}" for b, n in found.items())
    )
    assert BRICK_SEQUENCE not in payload


@pytest.mark.parametrize("theme,prompt", _all_dispatches())
def test_dispatch_fits_in_one_raster_command(theme, prompt):
    """No dispatch may exceed the printer's single-command raster limit.

    A 2400px dispatch desynced both printers mid-image — the firmware quit
    consuming pixel data, printed the rest as garbage text and ate the cut.
    Nothing in software detected it; the write succeeded and the soak
    reported ok. This is the only thing standing between a long prompt and
    two feet of noise.
    """
    parts = compose_parts(prompt, theme=theme, dispatch_num=1)

    for index, part in enumerate(parts):
        size = (part.width // 8) * part.height
        assert size <= MAX_RASTER_BYTES, (
            f"{theme}: part {index + 1}/{len(parts)} is {size:,} raster bytes, "
            f"over the {MAX_RASTER_BYTES:,} limit — shorten the prompt or the "
            f"layout. prompt: {prompt!r}"
        )


def test_sanitizer_catches_every_command_byte():
    """Direct check that each dangerous byte is actually rewritten."""
    raw = bytes(range(256))
    cleaned = _sanitize_raster(raw)

    assert len(cleaned) == len(raw)
    for b in COMMAND_BYTES:
        assert b not in cleaned, f"0x{b:02x} survived sanitizing"


def test_sanitizer_preserves_safe_bytes():
    """Only the four command bytes change — everything else passes through."""
    raw = bytes(range(256))
    cleaned = _sanitize_raster(raw)

    for original, result in zip(raw, cleaned):
        if original in COMMAND_BYTES:
            continue
        assert result == original, f"0x{original:02x} was altered to 0x{result:02x}"


def test_sanitizer_substitutes_adjacent_values():
    """Substitutions stay within one bit, so a swap moves a single pixel."""
    cleaned = _sanitize_raster(bytes(COMMAND_BYTES))

    for original, result in zip(COMMAND_BYTES, cleaned):
        distance = bin(original ^ result).count("1")
        assert distance == 1, (
            f"0x{original:02x} -> 0x{result:02x} flips {distance} bits; "
            "substitutions must stay visually imperceptible"
        )


def test_escape_targets_are_not_themselves_commands():
    """The bug that cost us a printer: escaping one command byte into another.

    The old table flipped bit 0 or 1, mapping ESC->SUB, FS->RS and GS->US —
    every one of them a live command — so a graphic dense in ESC/FS/GS emitted
    a burst of command bytes rather than none.
    """
    cleaned = _sanitize_raster(bytes(COMMAND_BYTES))

    for original, result in zip(COMMAND_BYTES, cleaned):
        assert result not in COMMAND_BYTES, (
            f"0x{original:02x} ({COMMAND_BYTES[original]}) escapes to "
            f"0x{result:02x} ({COMMAND_BYTES.get(result)}), which is itself a "
            "command byte — the sanitizer would be manufacturing commands"
        )


def test_brick_sequence_is_neutralised():
    """Direct check: the IAP trigger cannot survive sanitizing.

    Fast counterpart to the corpus sweep — feeds the sequence in explicitly
    rather than waiting for it to occur naturally in pixel data.
    """
    raw = b"\x00\xff" + BRICK_SEQUENCE + b"\xff\x00" + BRICK_SEQUENCE
    cleaned = _sanitize_raster(raw)

    assert BRICK_SEQUENCE not in cleaned
    assert b"\x18" not in cleaned
    assert b"\x19" not in cleaned


def test_sanitizing_is_idempotent():
    """Running the sanitizer twice must not reintroduce a command byte."""
    once = _sanitize_raster(bytes(range(256)))
    twice = _sanitize_raster(once)

    assert once == twice
