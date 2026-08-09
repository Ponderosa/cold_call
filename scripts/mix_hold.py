#!/usr/bin/env python3
"""Bake assets/audio/hold.wav — what the caller hears while waiting.

One asset does both jobs: the music under the wait, and the message
explaining it. It plays exactly once and fades out at the end; the hold
window is as long as this file. Do not loop it — the fade would recur every
minute, and the wait would never sound like it was ending.

The bed is "Local Forecast - Elevator" by Kevin MacLeod (incompetech.com),
licensed CC BY 3.0. See assets/audio/CREDITS.md. The mp3 is not committed;
it is freely downloadable and the licence only asks for attribution, so
there is no reason to carry 7MB of build input in the history forever.

Usage:
    uv run python scripts/mix_hold.py path/to/bed.mp3

Requires ffmpeg on PATH, for decoding only.
"""

from __future__ import annotations

import array
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "assets" / "audio"
MESSAGE = AUDIO_DIR / "hold_message.wav"
OUT = AUDIO_DIR / "hold.wav"

RATE = 48000

# The finished level. Lower than the narration clips, which sit at -3: this
# plays for a minute straight in someone's ear, and continuous music reads
# louder than speech at the same measured level because speech has gaps.
PEAK_DBFS = -6.0

# The bed, relative to the message. The message should sit where the other
# narration sits; only the music moves.
BED_DB = -8.0

# The bed has no fades — it starts and ends at full level — so the body can
# be taken from the top. LENGTH is the whole hold window.
BODY_START = 0.0
LENGTH = 60.0

# How many times the message recurs, and how far the bed ducks under it.
MSG_COUNT = 3
DUCK_DB = -9.0

# The hold state runs exactly one pass of this asset and then gives up, so it
# ends rather than repeats: the last few seconds fade out under the caller,
# which is the cue that the wait is over before the intercept message says so.
FADE_OUT = 4.0


def _decode(path: Path) -> array.array:
    """Decode anything ffmpeg reads into 48k stereo 16-bit samples."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "decoded.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path),
             "-ac", "2", "-ar", str(RATE), "-f", "wav", str(wav), "-y"],
            check=True,
        )
        return _read(wav)


def _read(path: Path) -> array.array:
    with wave.open(str(path)) as w:
        if (w.getframerate(), w.getsampwidth(), w.getnchannels()) != (RATE, 2, 2):
            raise SystemExit(f"{path.name}: need {RATE}Hz 16-bit stereo")
        samples = array.array("h")
        samples.frombytes(w.readframes(w.getnframes()))
        return samples


def _write(path: Path, samples: array.array) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[-3].strip())
    if not MESSAGE.exists():
        sys.exit(f"missing {MESSAGE.relative_to(ROOT)} — bake the narration first")

    bed = _decode(Path(sys.argv[1]))
    message = _read(MESSAGE)

    start = int(BODY_START * RATE) * 2
    length_n = int(LENGTH * RATE) * 2
    if len(bed) < start + length_n:
        sys.exit("bed is too short for LENGTH")

    out = array.array("h", bed[start:start + length_n])

    bed_gain = 10 ** (BED_DB / 20)
    for i in range(len(out)):
        out[i] = int(out[i] * bed_gain)

    # Lay the message in at even spacing, ducking the bed under each pass.
    duck = 10 ** (DUCK_DB / 20)
    for pass_index in range(MSG_COUNT):
        at = int((LENGTH / MSG_COUNT) * pass_index * RATE) * 2
        for i in range(0, len(message), 2):
            j = at + i
            if j + 1 >= length_n:
                break
            for ch in (0, 1):
                mixed = out[j + ch] * duck + message[i + ch]
                out[j + ch] = max(-32768, min(32767, int(mixed)))

    # Fade the tail so the asset ends rather than stops.
    fade_n = int(FADE_OUT * RATE) * 2
    for i in range(fade_n):
        j = len(out) - fade_n + i
        gain = math.cos((i / fade_n) * math.pi / 2) ** 2
        out[j] = int(out[j] * gain)

    peak = max(abs(s) for s in out) or 1
    gain = (10 ** (PEAK_DBFS / 20) * 32767) / peak
    for i in range(len(out)):
        out[i] = max(-32768, min(32767, int(out[i] * gain)))

    _write(OUT, out)
    print(f"  {OUT.relative_to(ROOT)}: {LENGTH:.0f}s, message x{MSG_COUNT}, "
          f"{FADE_OUT:.0f}s fade, peak {PEAK_DBFS} dBFS")


if __name__ == "__main__":
    main()
