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

import pytest

from cold_call.printer import _compose_dispatch, _print_raster, _sanitize_raster
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
HEADER_LEN = 8


class _CapturePrinter:
    """Stands in for escpos File, keeping the bytes _print_raster emits."""

    def __init__(self):
        self.data = b""

    def _raw(self, payload):
        self.data += payload


def _raster_payload(prompt: str, theme: str) -> bytes:
    """Return the pixel bytes for a dispatch, exactly as sent to the printer."""
    dispatch = _compose_dispatch(prompt, theme=theme, dispatch_num=1)
    cap = _CapturePrinter()
    _print_raster(cap, dispatch.rotate(180))
    return cap.data[HEADER_LEN:]


def _all_dispatches():
    """Every (theme, prompt) pair the installation can print."""
    for theme in DEPARTMENTS:
        for prompt in load_prompts(theme):
            yield theme, prompt


def test_corpus_is_fully_loaded():
    """Guard the sweep itself — an empty corpus would pass every test below."""
    pairs = list(_all_dispatches())
    assert len(pairs) >= 175, f"expected the full corpus, got {len(pairs)} dispatches"

    themes_seen = {theme for theme, _ in pairs}
    assert themes_seen == set(DEPARTMENTS), f"missing departments: {set(DEPARTMENTS) - themes_seen}"


@pytest.mark.parametrize("theme,prompt", _all_dispatches())
def test_no_command_bytes_in_raster(theme, prompt):
    """No dispatch may emit a command-initiator byte in its pixel data."""
    payload = _raster_payload(prompt, theme)

    found = {b: payload.count(b) for b in COMMAND_BYTES if b in payload}
    assert not found, (
        f"{theme}: raster contains command bytes "
        + ", ".join(f"0x{b:02x} ({COMMAND_BYTES[b]}) x{n}" for b, n in found.items())
        + f" — prompt: {prompt!r}"
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


def test_sanitizing_is_idempotent():
    """Running the sanitizer twice must not reintroduce a command byte."""
    once = _sanitize_raster(bytes(range(256)))
    twice = _sanitize_raster(once)

    assert once == twice
