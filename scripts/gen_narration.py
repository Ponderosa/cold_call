#!/usr/bin/env python3
"""Synthesize the narration clips in assets/audio/ with Piper TTS.

The voice is en_US-amy-medium, the same one the existing announcements
(connecting.wav, not_in_service.wav) were cut with. Piper writes 22.05kHz
mono; the POP Phone playback path is fixed at 48kHz 16-bit stereo (see
RATE/FORMAT in cold_call.audio), so every clip is resampled, duplicated to
both channels, and peak-normalized to -3 dBFS to sit with the sound effects.

One-time setup (outside the project venv — onnxruntime and the 63MB voice
model have no business on the Pi):

    python3 -m venv ~/.venvs/piper
    ~/.venvs/piper/bin/pip install piper-tts
    ~/.venvs/piper/bin/python -m piper.download_voices en_US-amy-medium

Usage:
    PIPER=~/.venvs/piper/bin/piper python3 scripts/gen_narration.py
    PIPER=... python3 scripts/gen_narration.py both_present  # one clip

Set PIPER_DATA_DIR if the voice lives somewhere other than Piper's default
data directory. Requires ffmpeg on PATH.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "audio"

VOICE = "en_US-amy-medium"

# Match the existing sound effects: 48kHz S16_LE stereo, peaks near -3 dBFS.
RATE = 48000
PEAK_DBFS = -3.0

BRIEFING = (
    "Greetings from the Seattle Municipal Office of Social Climate. "
    "You've been contracted by one of our sub-agencies to investigate a "
    "particular aspect of the social phenomenon known as the Seattle Freeze. "
    "You will soon be connected to a fellow investigator and given a printed "
    "questionnaire. Read the question aloud to them, then document their "
    "response on your questionnaire using the writing instruments provided, "
    "before posting your form to the board with an adhesive seal."
)

# pad_to holds a clip open with trailing silence when it has to cover a
# fixed stretch of the session. Only both_present needs it: it plays to the
# caller while the receiver hears its own dial tone (2.5s, session.py) plus
# dtmf_dial.wav (1.6s), and should still be going when that dialing lands.
CLIPS = [
    ("hold_message", "This call requires another participant "
                     "to continue holding the line.", None),
    ("both_present", "Both participants are now present.", 4.1),
    ("briefing", BRIEFING, None),
    ("printing_questionnaire", "Printing your questionnaire now.", None),
]


def piper_cmd() -> list[str]:
    """The Piper invocation — $PIPER, the CLI on PATH, or the module."""
    override = os.environ.get("PIPER")
    if override:
        return [os.path.expanduser(override)]
    if shutil.which("piper"):
        return ["piper"]
    return [sys.executable, "-m", "piper"]


def synthesize(text: str, dest: Path) -> None:
    """Raw Piper output — 22.05kHz mono — for one clip."""
    cmd = piper_cmd() + ["-m", VOICE, "-f", str(dest)]
    data_dir = os.environ.get("PIPER_DATA_DIR")
    if data_dir:
        cmd += ["--data-dir", os.path.expanduser(data_dir)]
    subprocess.run(cmd, input=text, text=True, check=True,
                   stdout=subprocess.DEVNULL)


def peak_dbfs(path: Path) -> float:
    """Peak level of a file, from ffmpeg's volumedetect."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    for line in out.splitlines():
        if "max_volume:" in line:
            return float(line.split("max_volume:")[1].strip().split()[0])
    raise RuntimeError(f"no max_volume in ffmpeg output for {path}")


def conform(src: Path, dest: Path, pad_to: float | None) -> None:
    """Resample, spread to stereo, normalize, and pad out to length."""
    chain = [f"aresample={RATE}", "pan=stereo|c0=c0|c1=c0",
             f"volume={PEAK_DBFS - peak_dbfs(src):.2f}dB"]
    if pad_to:
        chain.append(f"apad=whole_dur={pad_to}")

    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-af", ",".join(chain), "-c:a", "pcm_s16le", str(dest)],
        check=True,
    )


def main():
    wanted = set(sys.argv[1:])
    clips = [c for c in CLIPS if not wanted or c[0] in wanted]
    if not clips:
        print(f"No such clip. Known: {', '.join(c[0] for c in CLIPS)}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        for name, text, pad_to in clips:
            raw = Path(tmp) / f"{name}.raw.wav"
            out = OUT_DIR / f"{name}.wav"
            synthesize(text, raw)
            conform(raw, out, pad_to)

            frames = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "csv=p=0", str(out)],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            print(f"  {out.name}: {float(frames):.2f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
