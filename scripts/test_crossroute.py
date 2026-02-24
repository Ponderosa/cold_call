#!/usr/bin/env python3
"""Cross-route two USB audio devices using pyalsaaudio.

Single process, two threads (one per direction). Direct ALSA access.

Usage:
    uv run python scripts/test_crossroute.py
    Ctrl-C to stop.
"""

import sys
import threading
import alsaaudio

RATE = 48000
PERIOD = 1024  # frames per read/write (~21ms)

# Device names to search for (substrings of ALSA card names)
DEVICE_A = "POP Phone"
DEVICE_B = "Scarlett"


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


def open_pcm(card: int, channels: int, capture: bool) -> alsaaudio.PCM:
    return alsaaudio.PCM(
        type=alsaaudio.PCM_CAPTURE if capture else alsaaudio.PCM_PLAYBACK,
        mode=alsaaudio.PCM_NORMAL,
        device=f"plughw:{card},0",
        channels=channels,
        rate=RATE,
        format=alsaaudio.PCM_FORMAT_S16_LE,
        periodsize=PERIOD,
    )


def route(cap: alsaaudio.PCM, play: alsaaudio.PCM, label: str,
          stop_event: threading.Event):
    """Read from cap, write to play."""
    while not stop_event.is_set():
        try:
            n, data = cap.read()
            if n > 0:
                play.write(data)
        except Exception as e:
            print(f"{label}: {e}", file=sys.stderr)
            break


def main():
    card_a = find_card(DEVICE_A)
    card_b = find_card(DEVICE_B)

    if card_a is None:
        print(f"ERROR: {DEVICE_A} not found")
        sys.exit(1)
    if card_b is None:
        print(f"ERROR: {DEVICE_B} not found")
        sys.exit(1)

    print(f"{DEVICE_A}: card {card_a}")
    print(f"{DEVICE_B}: card {card_b}")
    print(f"Rate: {RATE}  Period: {PERIOD} frames ({PERIOD / RATE * 1000:.0f}ms)")
    print()

    # Both use stereo S16_LE via plughw (ALSA converts Scarlett's S32_LE)
    cap_a = open_pcm(card_a, 2, capture=True)
    play_a = open_pcm(card_a, 2, capture=False)
    cap_b = open_pcm(card_b, 2, capture=True)
    play_b = open_pcm(card_b, 2, capture=False)

    stop = threading.Event()

    t1 = threading.Thread(
        target=route,
        args=(cap_a, play_b, f"{DEVICE_A}→{DEVICE_B}", stop),
        daemon=True,
    )
    t2 = threading.Thread(
        target=route,
        args=(cap_b, play_a, f"{DEVICE_B}→{DEVICE_A}", stop),
        daemon=True,
    )

    t1.start()
    t2.start()

    print("Cross-route active. Ctrl-C to stop.")
    print()

    try:
        t1.join()
    except KeyboardInterrupt:
        print("\nStopping.")
        stop.set()

    cap_a.close()
    play_a.close()
    cap_b.close()
    play_b.close()


if __name__ == "__main__":
    main()
