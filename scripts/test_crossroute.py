#!/usr/bin/env python3
"""Cross-route two USB audio devices.

Audio hot path: arecord|aplay subprocesses (pure C, no Python in the loop).
Python handles: device discovery, mixer setup, subprocess lifecycle.

POP Phone (SYNC, stereo) <-> Blackwire 5220 (ASYNC cap mono, ADAPTIVE play stereo)
Devices on separate USB controllers (VL805 + DWC2).

Usage:
    uv run python scripts/test_crossroute.py
    Ctrl-C to stop.
"""

import atexit
import os
import signal
import subprocess
import sys
import time

import alsaaudio

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

# Device names (substrings matched against ALSA card names)
DEVICE_A = "POP Phone"
DEVICE_B = "Blackwire"


def find_card(name_fragment: str) -> int | None:
    """Find ALSA card number by name substring."""
    for i in range(10):
        try:
            name, longname = alsaaudio.card_name(i)
            if name_fragment.lower() in name.lower() or name_fragment.lower() in longname.lower():
                return i
        except Exception:
            continue
    return None


def setup_mixer(card: int, device_name: str):
    """Configure mixer levels for clean cross-route."""
    try:
        mixers = alsaaudio.mixers(cardindex=card)
    except Exception:
        return

    if device_name == "Blackwire":
        if "Sidetone" in mixers:
            m = alsaaudio.Mixer("Sidetone", cardindex=card)
            m.setmute(1)
            m.setvolume(0)
            print(f"  card {card}: Sidetone muted")
        if "Headset" in mixers:
            m = alsaaudio.Mixer("Headset", cardindex=card)
            m.setvolume(80)
            print(f"  card {card}: Headset playback → 80%")

    elif device_name == "POP Phone":
        if "PCM" in mixers:
            m = alsaaudio.Mixer("PCM", cardindex=card)
            m.setvolume(80)
            print(f"  card {card}: PCM playback → 80%")
        if "Mic" in mixers:
            m = alsaaudio.Mixer("Mic", cardindex=card)
            m.setvolume(80)
            print(f"  card {card}: Mic capture → 80%")
        if "Auto Gain Control" in mixers:
            m = alsaaudio.Mixer("Auto Gain Control", cardindex=card)
            m.setmute(0)
            print(f"  card {card}: AGC off")


def start_pipe(cap_card: int, play_card: int, label: str) -> subprocess.Popen:
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
    card_a = find_card(DEVICE_A)
    card_b = find_card(DEVICE_B)

    if card_a is None:
        sys.exit(f"ERROR: '{DEVICE_A}' not found")
    if card_b is None:
        sys.exit(f"ERROR: '{DEVICE_B}' not found")

    print(f"Devices:")
    print(f"  A: {DEVICE_A} (card {card_a})")
    print(f"  B: {DEVICE_B} (card {card_b})")
    print(f"  Rate: {RATE} Hz, Period: {PERIOD} ({PERIOD / RATE * 1000:.0f}ms), "
          f"Buffer: {BUFFER} ({BUFFER / RATE * 1000:.0f}ms)")
    print()

    print("Mixer setup:")
    setup_mixer(card_a, DEVICE_A)
    setup_mixer(card_b, DEVICE_B)
    print()

    print("Starting audio pipes:")
    rec_ab, play_ab = start_pipe(card_a, card_b, f"{DEVICE_A} → {DEVICE_B}")
    rec_ba, play_ba = start_pipe(card_b, card_a, f"{DEVICE_B} → {DEVICE_A}")
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
