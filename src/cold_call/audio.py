"""Audio subsystem for Cold Calls.

Handles:
- Playing WAV files to individual handsets (dial tone, ring, DTMF, announcements)
- Cross-routing audio between two handsets (arecord|aplay subprocess pipes)
- Background music playback mixed into both handsets

All audio goes through aplay subprocesses — Python never touches PCM data.
"""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import alsaaudio

if TYPE_CHECKING:
    from cold_call.hardware import Side

_libc = ctypes.CDLL("libc.so.6")


def _set_pdeathsig():
    """Ensure child process dies when parent exits (Linux-specific)."""
    _libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG = 1


RATE = 48000
PERIOD = 1024
BUFFER = 4096
FORMAT = "S16_LE"

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
AUDIO_DIR = ASSETS / "audio"


def setup_mixer(side: Side):
    """Configure POP Phone mixer levels for a side."""
    card = side.card
    try:
        mixers = alsaaudio.mixers(cardindex=card)
    except Exception:
        return

    if "PCM" in mixers:
        m = alsaaudio.Mixer("PCM", cardindex=card)
        m.setvolume(100)
    if "Mic" in mixers:
        m = alsaaudio.Mixer("Mic", cardindex=card)
        m.setvolume(100)
    if "Auto Gain Control" in mixers:
        m = alsaaudio.Mixer("Auto Gain Control", cardindex=card)
        m.setmute(0)




class SoundPlayer:
    """Plays a WAV file to a specific side's earpiece. Non-blocking, stoppable."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    def play(self, side: Side, wav_path: str | Path, loop: bool = False):
        """Start playing a WAV file. Stops any currently playing sound first."""
        self.stop()
        path = str(wav_path)

        def _preexec():
            os.setpgrp()  # new process group so we can kill the whole tree
            _set_pdeathsig()

        if loop:
            # Loop raw PCM: strip 44-byte WAV header, play as raw so aplay
            # doesn't stop at the WAV-declared length
            cmd = (
                f"while true; do tail -c +45 '{path}'; done "
                f"| aplay -D plughw:{side.card},0 -c 2 -r {RATE} -f {FORMAT} -t raw"
                f" --buffer-size {BUFFER} --period-size {PERIOD}"
            )
            self._proc = subprocess.Popen(
                cmd, shell=True, stderr=subprocess.DEVNULL,
                preexec_fn=_preexec,
            )
        else:
            self._proc = subprocess.Popen(
                ["aplay", "-D", f"plughw:{side.card},0",
                 "--buffer-size", str(BUFFER), "--period-size", str(PERIOD),
                 path],
                stderr=subprocess.DEVNULL,
                preexec_fn=_preexec,
            )

    def stop(self):
        """Stop the current sound if playing."""
        if self._proc is not None:
            try:
                # Kill the entire process group (shell + aplay + cat)
                os.killpg(self._proc.pid, signal.SIGTERM)
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(self._proc.pid, signal.SIGKILL)
                    self._proc.wait(timeout=1)
                except Exception:
                    pass
            self._proc = None

    def is_playing(self) -> bool:
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def wait(self):
        """Block until the current sound finishes."""
        if self._proc is not None:
            self._proc.wait()
            self._proc = None


# Inline mixer subprocess — reads mic PCM from stdin, mixes in a looping
# music WAV file, writes mixed PCM to stdout.  Runs in its own process to
# keep Python out of the audio hot path in the main process.
_MIXER_CODE = """
import sys, array

CHUNK = 1024 * 4  # period_size * frame_size (2ch * 2bytes)

music_path = sys.argv[1]
music_vol = float(sys.argv[2])

with open(music_path, 'rb') as f:
    f.read(44)  # skip WAV header
    music_data = f.read()

music_pos = 0

while True:
    mic = sys.stdin.buffer.read(CHUNK)
    if not mic:
        break

    n_bytes = len(mic)

    # Get music chunk, looping
    music_chunk = bytearray()
    remaining = n_bytes
    while remaining > 0:
        available = len(music_data) - music_pos
        take = min(remaining, available)
        music_chunk.extend(music_data[music_pos:music_pos + take])
        music_pos += take
        if music_pos >= len(music_data):
            music_pos = 0
        remaining -= take

    # Mix samples
    mic_samples = array.array('h')
    mic_samples.frombytes(mic)
    music_samples = array.array('h')
    music_samples.frombytes(bytes(music_chunk))

    out = array.array('h', [
        max(-32768, min(32767, int(m + v * music_vol)))
        for m, v in zip(mic_samples, music_samples)
    ])

    sys.stdout.buffer.write(out.tobytes())
    sys.stdout.buffer.flush()
"""


class CrossRoute:
    """Bidirectional audio cross-route between two sides.

    Optionally mixes a background music file into both earpieces via an
    inline Python mixer subprocess: arecord | mixer | aplay.  All playback
    goes through plughw (no dmix) to avoid DWC2 crackle.
    """

    def __init__(self):
        self._procs: list[subprocess.Popen] = []

    def start(self, side_a: Side, side_b: Side,
              music_path: str | Path | None = None, music_volume: float = 0.3):
        """Start cross-routing: Mic A → Earpiece B, Mic B → Earpiece A.

        If music_path is given, mixes that WAV file (looping) into both
        earpieces at the given volume (0.0–1.0).
        """
        self.stop()
        self._procs = []

        # Always create pipes in card-number order so each USB controller
        # opens capture before playback — DWC2 crackles if reversed.
        pairs = sorted(
            [(side_a, side_b), (side_b, side_a)],
            key=lambda pair: pair[0].card,
        )
        for cap, play in pairs:
            arecord = [
                "arecord",
                "-D", f"plughw:{cap.card},0",
                "-c", "2", "-r", str(RATE), "-f", FORMAT, "-t", "raw",
                "--buffer-size", str(BUFFER), "--period-size", str(PERIOD),
            ]
            aplay = [
                "aplay",
                "-D", f"plughw:{play.card},0",
                "-c", "2", "-r", str(RATE), "-f", FORMAT, "-t", "raw",
                "--buffer-size", str(BUFFER), "--period-size", str(PERIOD),
            ]

            rec = subprocess.Popen(
                arecord, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                preexec_fn=_set_pdeathsig,
            )

            if music_path:
                mixer = subprocess.Popen(
                    [sys.executable, "-c", _MIXER_CODE,
                     str(music_path), str(music_volume)],
                    stdin=rec.stdout, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=_set_pdeathsig,
                )
                rec.stdout.close()
                plr = subprocess.Popen(
                    aplay, stdin=mixer.stdout, stderr=subprocess.DEVNULL,
                    preexec_fn=_set_pdeathsig,
                )
                mixer.stdout.close()
                self._procs.extend([rec, mixer, plr])
            else:
                plr = subprocess.Popen(
                    aplay, stdin=rec.stdout, stderr=subprocess.DEVNULL,
                    preexec_fn=_set_pdeathsig,
                )
                rec.stdout.close()
                self._procs.extend([rec, plr])

    def stop(self):
        """Stop the cross-route."""
        for p in self._procs:
            try:
                p.terminate()
            except OSError:
                pass
        for p in self._procs:
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except OSError:
                    pass
        self._procs = []

    def is_active(self) -> bool:
        return len(self._procs) > 0 and all(p.poll() is None for p in self._procs)
