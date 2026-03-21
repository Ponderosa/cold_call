#!/usr/bin/env python3
"""Cross-route two POP Phone USB handsets.

Audio hot path: arecord|aplay subprocesses (pure C, no Python in the loop).
Python handles: device discovery, mixer setup, subprocess lifecycle.

Phones are paired with printers by USB bus via cold_call.hardware.

Usage:
    uv run python scripts/test_crossroute.py
    Ctrl-C to stop.
"""

import atexit
import signal
import subprocess
import sys
import time

from cold_call.hardware import discover_sides, setup_pop_phone_mixer

# Ensure child processes die when parent is killed (Linux-specific).
# PR_SET_PDEATHSIG makes the kernel send SIGTERM to children when parent exits.
import ctypes
_libc = ctypes.CDLL("libc.so.6")
def _set_pdeathsig():
    _libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG = 1

# --- Audio config ---
RATE = 48000
PERIOD = 1024       # ~21ms
BUFFER = 4096       # ~85ms — 4 periods of headroom
FORMAT = "S16_LE"


def start_pipe(cap_card: int, play_card: int, label: str) -> tuple:
    """Start an arecord|aplay pipe between two ALSA devices."""
    arecord = [
        "arecord",
        "-D", f"plughw:{cap_card},0",
        "-c", "2",
        "-r", str(RATE),
        "-f", FORMAT,
        "-t", "raw",
        "--buffer-size", str(BUFFER),
        "--period-size", str(PERIOD),
    ]
    aplay = [
        "aplay",
        "-D", f"plughw:{play_card},0",
        "-c", "2",
        "-r", str(RATE),
        "-f", FORMAT,
        "-t", "raw",
        "--buffer-size", str(BUFFER),
        "--period-size", str(PERIOD),
    ]

    rec = subprocess.Popen(arecord, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           preexec_fn=_set_pdeathsig)
    play = subprocess.Popen(aplay, stdin=rec.stdout, stderr=subprocess.DEVNULL,
                            preexec_fn=_set_pdeathsig)
    # Allow rec to receive SIGPIPE if play dies
    rec.stdout.close()

    print(f"  {label}: arecord(pid={rec.pid}) | aplay(pid={play.pid})")
    return rec, play


def main():
    sides = discover_sides()

    if len(sides) < 2:
        sys.exit(f"ERROR: Need 2 sides, found {len(sides)}")

    a, b = sides[0], sides[1]

    print(f"\nDevices:")
    print(f"  Side A: card {a.card} ({a.card_id}) + {a.printer_dev}")
    print(f"  Side B: card {b.card} ({b.card_id}) + {b.printer_dev}")
    print(f"  Rate: {RATE} Hz, Period: {PERIOD} ({PERIOD / RATE * 1000:.0f}ms), "
          f"Buffer: {BUFFER} ({BUFFER / RATE * 1000:.0f}ms)")
    print()

    print("Mixer setup:")
    setup_pop_phone_mixer(a.card)
    setup_pop_phone_mixer(b.card)
    print()

    print("Starting audio pipes:")
    rec_ab, play_ab = start_pipe(a.card, b.card, f"Side A -> Side B")
    rec_ba, play_ba = start_pipe(b.card, a.card, f"Side B -> Side A")
    print()

    procs = [rec_ab, play_ab, rec_ba, play_ba]

    def cleanup():
        for p in procs:
            try:
                p.terminate()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print("Cross-route active. Ctrl-C to stop.\n")

    try:
        while True:
            dead = [p for p in procs if p.poll() is not None]
            for p in dead:
                print(f"WARNING: pid {p.pid} exited with code {p.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")

    cleanup()
    print("Done.")


if __name__ == "__main__":
    main()
