#!/usr/bin/env python3
"""Bake assets/audio/hold_loop.wav — the caller's on-hold bed.

One asset does both jobs: the music the caller hears while the receiver's
printer buzzes, and the "another participant" message recurring over it.
audio.py plays it with loop=True, so it has to survive being butt-spliced
end to start.

The source is a 60s AI-generated track that fades in and out. Both fades are
cut away and only the steady body (BODY_START..BODY_END) is used; the loop
seam is a constant-power crossfade of that body's tail back into its head,
which is why the result is XFADE shorter than the body. The message is laid
in MSG_COUNT times at even spacing, wrapping across the seam, and the bed
ducks under each pass.

Output matches the other clips: 48kHz 16-bit stereo, peak -3 dBFS.

Usage:
    python3 scripts/mix_hold_loop.py

Requires ffmpeg on PATH. Regenerate hold_message.wav first if its wording
changed — this bakes in whatever is on disk.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "assets" / "audio"
SOURCE = AUDIO_DIR / "sources" / "hold_music_source.wav"
MESSAGE = AUDIO_DIR / "hold_message.wav"
OUT = AUDIO_DIR / "hold_loop.wav"

RATE = 48000
PEAK_DBFS = -3.0

# The source sits at a steady ~-16.5 dBFS RMS between these marks; outside
# them it is fading in or out, and splicing a fade to a fade left an audible
# 20dB trough at the loop point.
BODY_START = 14.0
BODY_END = 57.0
XFADE = 3.0
LOOP = (BODY_END - BODY_START) - XFADE

# Bed level under the voice, then how hard it steps back while she speaks.
BED_DB = -12.0
DUCK = "threshold=0.03:ratio=6:attack=25:release=350"

# A little music before the first message, then evenly spaced — the spacing
# divides the loop exactly, so the wrap around the seam matches the others.
MSG_LEAD = 1.5
MSG_COUNT = 3


def run(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True)


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


def build_bed(dest: Path) -> None:
    """The music alone, trimmed to its body and closed into a loop."""
    run(["-i", str(SOURCE), "-filter_complex",
         f"[0:a]atrim={BODY_START}:{BODY_END},asetpts=N/SR/TB,asplit=2[a][b];"
         f"[a]atrim={XFADE},asetpts=N/SR/TB[body];"
         f"[b]atrim=0:{XFADE},asetpts=N/SR/TB[head];"
         # qsin holds the energy flat across the splice; a linear fade dipped
         # ~4dB in the middle, since the two sides are unrelated material.
         f"[body][head]acrossfade=d={XFADE}:c1=qsin:c2=qsin[bed]",
         "-map", "[bed]", "-ar", str(RATE), "-c:a", "pcm_s16le", str(dest)])


def build_voice(dest: Path) -> None:
    """The message repeated across the length of the loop."""
    spacing = LOOP / MSG_COUNT
    copies = "".join(f"[v{i}]" for i in range(MSG_COUNT))
    delays = ";".join(
        f"[v{i}]adelay={int((MSG_LEAD + i * spacing) * 1000)}:all=1[m{i}]"
        for i in range(MSG_COUNT)
    )
    mix = "".join(f"[m{i}]" for i in range(MSG_COUNT))

    run(["-i", str(MESSAGE), "-filter_complex",
         f"[0:a]asplit={MSG_COUNT}{copies};{delays};"
         f"{mix}amix=inputs={MSG_COUNT}:normalize=0,"
         f"apad=whole_dur={LOOP},atrim=0:{LOOP}[voice]",
         "-map", "[voice]", "-ar", str(RATE), "-c:a", "pcm_s16le", str(dest)])


def mix(bed: Path, voice: Path, dest: Path) -> None:
    """Duck the bed under the voice and sum, at 32-bit float for headroom."""
    run(["-i", str(bed), "-i", str(voice), "-filter_complex",
         f"[0:a]volume={BED_DB}dB[quiet];"
         # sidechaincompress drops the last half second of its main input,
         # which would nick the crossfade, so pad back out to the full loop.
         f"[quiet][1:a]sidechaincompress={DUCK},"
         f"apad,atrim=0:{LOOP},asetpts=N/SR/TB[ducked];"
         f"[ducked][1:a]amix=inputs=2:normalize=0[mix]",
         "-map", "[mix]", "-c:a", "pcm_f32le", str(dest)])


def main():
    if not SOURCE.exists():
        print(f"Missing {SOURCE.relative_to(ROOT)}")
        return 1
    if not MESSAGE.exists():
        print(f"Missing {MESSAGE.relative_to(ROOT)} — run gen_narration.py first")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bed, voice, raw = tmp / "bed.wav", tmp / "voice.wav", tmp / "mix.wav"

        build_bed(bed)
        build_voice(voice)
        mix(bed, voice, raw)

        # Summing voice over bed overshoots; the float intermediate holds it
        # undistorted so this pass can just scale the whole thing down.
        run(["-i", str(raw), "-af", f"volume={PEAK_DBFS - peak_dbfs(raw):.2f}dB",
             "-c:a", "pcm_s16le", str(OUT)])

    print(f"  {OUT.name}: {LOOP:.2f}s loop, "
          f"{MSG_COUNT} messages every {LOOP / MSG_COUNT:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
