#!/usr/bin/env python3
"""Interactive scenario tester for Cold Calls.

Tests each session phase independently so you can isolate audio issues.
Uses keyboard input (A/B to toggle hook, number keys to pick a scenario).

Stop the service first:  sudo systemctl stop cold-call
Run:                     uv run python scripts/test_scenarios.py
"""

from __future__ import annotations

import subprocess
import sys
import termios
import time
import tty
import select

from cold_call.hardware import discover_sides
from cold_call.audio import SoundPlayer, CrossRoute, setup_mixer, AUDIO_DIR


def read_key(timeout: float = 0.1) -> str | None:
    """Non-blocking single keypress read."""
    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.read(1)
    return None


def wait_for_key(prompt: str = "") -> str:
    """Block until a key is pressed."""
    if prompt:
        print(prompt, end="", flush=True)
    while True:
        ch = read_key(0.2)
        if ch:
            print()
            return ch


def wait_for_toggle(sides_state: dict, label: str, want_off_hook: bool):
    """Wait for a side to be toggled to the desired state."""
    want = "pick up" if want_off_hook else "hang up"
    print(f"  >> Press {label} to {want} Side {label}")
    while True:
        ch = read_key(0.1)
        if ch and ch.upper() == label:
            sides_state[label] = not sides_state[label]
            state = "OFF HOOK" if sides_state[label] else "ON HOOK"
            print(f"  Side {label}: {state}")
            if sides_state[label] == want_off_hook:
                return


def wait_for_any_toggle(sides_state: dict) -> str:
    """Wait for any side to be toggled. Returns the label."""
    print("  >> Press A or B to toggle")
    while True:
        ch = read_key(0.1)
        if ch and ch.upper() in ("A", "B"):
            label = ch.upper()
            sides_state[label] = not sides_state[label]
            state = "OFF HOOK" if sides_state[label] else "ON HOOK"
            print(f"  Side {label}: {state}")
            return label


def print_menu():
    print()
    print("=== Cold Calls Scenario Tester ===")
    print()
    print("  1  Full call: A calls, B answers, A hangs up (B hears busy tone)")
    print("  2  Full call: A calls, B answers, B hangs up (A hears busy tone)")
    print("  3  Early pickup: A calls, B picks up during dial tone")
    print("  4  Early pickup: A calls, B picks up during DTMF")
    print("  5  No answer: A calls, ring times out")
    print("  6  Caller abandons: A calls, A hangs up during ring")
    print("  7  Sound check: play each sound effect to each side")
    print("  8  Cross-route only: just voice, no effects")
    print("  9  Cross-route + background music")
    print("  q  Quit")
    print()


def scenario_full_call(a, b, player_a, player_b, crossroute, hangup_side: str):
    """Full call flow. hangup_side determines who hangs up first."""
    other = "B" if hangup_side == "A" else "A"
    caller, receiver = (a, b)
    caller_player, receiver_player = (player_a, player_b)
    sides_state = {"A": False, "B": False}

    print(f"\n--- Full call: A calls B, {hangup_side} hangs up ---")

    # Caller pickup
    wait_for_toggle(sides_state, "A", True)

    print("  Playing dial tone...")
    caller_player.play(a, AUDIO_DIR / "dial_tone.wav")
    time.sleep(2.5)
    caller_player.stop()

    print("  Dialing...")
    caller_player.play(a, AUDIO_DIR / "dtmf_dial.wav")
    caller_player.wait()

    print("  Ringing both sides...")
    caller_player.play(a, AUDIO_DIR / "ring_long.wav", loop=True)
    receiver_player.play(b, AUDIO_DIR / "ring_long.wav", loop=True)

    # Wait for B to pick up
    wait_for_toggle(sides_state, "B", True)
    caller_player.stop()
    receiver_player.stop()
    time.sleep(0.2)

    # Announcement first, then cross-route (avoids DWC2 dmix crackle)
    print("  Connecting...")
    caller_player.play(a, AUDIO_DIR / "connecting.wav")
    receiver_player.play(b, AUDIO_DIR / "connecting.wav")
    caller_player.wait()
    receiver_player.stop()
    time.sleep(0.2)

    crossroute.start(a, b)
    print("  CALL CONNECTED — talk!")

    # Wait for hangup_side to hang up
    wait_for_toggle(sides_state, hangup_side, False)

    print("  Hanging up...")
    crossroute.stop()

    # Play busy tone to the side still off hook
    still_off = other
    still_player = player_a if still_off == "A" else player_b
    still_side = a if still_off == "A" else b
    print(f"  Side {still_off} still off hook — playing busy tone (loops until hangup)")
    still_player.play(still_side, AUDIO_DIR / "busy_tone.wav", loop=True)

    # Wait for other side to hang up
    wait_for_toggle(sides_state, still_off, False)
    still_player.stop()
    print("  Both on hook. Done.")


def scenario_early_pickup(a, b, player_a, player_b, crossroute, during: str):
    """B picks up during dial tone or DTMF."""
    sides_state = {"A": False, "B": False}

    print(f"\n--- Early pickup during {during} ---")

    wait_for_toggle(sides_state, "A", True)

    if during == "dial_tone":
        print("  Playing dial tone... pick up B now!")
        player_a.play(a, AUDIO_DIR / "dial_tone.wav")
        wait_for_toggle(sides_state, "B", True)
        player_a.stop()
    elif during == "dtmf":
        print("  Playing dial tone...")
        player_a.play(a, AUDIO_DIR / "dial_tone.wav")
        time.sleep(2.5)
        player_a.stop()
        print("  Dialing... pick up B now!")
        player_a.play(a, AUDIO_DIR / "dtmf_dial.wav")
        wait_for_toggle(sides_state, "B", True)
        player_a.stop()

    time.sleep(0.2)

    # Announcement first, then cross-route (avoids DWC2 dmix crackle)
    print("  Connecting...")
    player_a.play(a, AUDIO_DIR / "connecting.wav")
    player_b.play(b, AUDIO_DIR / "connecting.wav")
    player_a.wait()
    player_b.stop()
    time.sleep(0.2)

    crossroute.start(a, b)
    print("  CALL CONNECTED — talk! Press A or B to hang up.")

    label = wait_for_any_toggle(sides_state)
    print("  Hanging up...")
    crossroute.stop()

    other = "B" if label == "A" else "A"
    if sides_state[other]:
        other_player = player_a if other == "A" else player_b
        other_side = a if other == "A" else b
        print(f"  Side {other} still off hook — playing busy tone")
        other_player.play(other_side, AUDIO_DIR / "busy_tone.wav", loop=True)
        wait_for_toggle(sides_state, other, False)
        other_player.stop()

    print("  Done.")


def scenario_no_answer(a, b, player_a, player_b):
    """A calls, nobody answers, ring times out."""
    sides_state = {"A": False, "B": False}

    print("\n--- No answer (ring timeout 10s) ---")

    wait_for_toggle(sides_state, "A", True)

    print("  Playing dial tone...")
    player_a.play(a, AUDIO_DIR / "dial_tone.wav")
    time.sleep(2.5)
    player_a.stop()

    print("  Dialing...")
    player_a.play(a, AUDIO_DIR / "dtmf_dial.wav")
    player_a.wait()

    print("  Ringing (10s timeout)...")
    player_a.play(a, AUDIO_DIR / "ring_long.wav", loop=True)
    player_b.play(b, AUDIO_DIR / "ring_long.wav", loop=True)

    # Wait 10s, checking for early keypress
    for _ in range(100):
        ch = read_key(0.1)
        if ch and ch.upper() == "B":
            # They answered — just stop early
            sides_state["B"] = True
            print("  Side B picked up (answering instead of timing out)")
            break
    else:
        print("  Ring timeout!")

    player_a.stop()
    player_b.stop()

    if not sides_state["B"]:
        print("  Playing busy tone to caller...")
        player_a.play(a, AUDIO_DIR / "busy_tone.wav", loop=True)
        wait_for_toggle(sides_state, "A", False)
        player_a.stop()

    print("  Done.")


def scenario_caller_abandons(a, b, player_a, player_b):
    """A calls, then hangs up during ring."""
    sides_state = {"A": False, "B": False}

    print("\n--- Caller abandons during ring ---")

    wait_for_toggle(sides_state, "A", True)

    print("  Playing dial tone...")
    player_a.play(a, AUDIO_DIR / "dial_tone.wav")
    time.sleep(2.5)
    player_a.stop()

    print("  Dialing...")
    player_a.play(a, AUDIO_DIR / "dtmf_dial.wav")
    player_a.wait()

    print("  Ringing... press A to hang up")
    player_a.play(a, AUDIO_DIR / "ring_long.wav", loop=True)
    player_b.play(b, AUDIO_DIR / "ring_long.wav", loop=True)

    wait_for_toggle(sides_state, "A", False)
    player_a.stop()
    player_b.stop()
    print("  Caller hung up. Done.")


def scenario_sound_check(a, b, player_a, player_b):
    """Play each sound effect to each side, one at a time."""
    sounds = [
        ("dial_tone.wav", "Dial tone", 3),
        ("dtmf_dial.wav", "DTMF dial", None),
        ("ring_long.wav", "Ring", 4),
        ("connecting.wav", "Connecting", None),
        ("busy_tone.wav", "Busy tone", 4),
    ]

    print("\n--- Sound check ---")
    for filename, name, duration in sounds:
        path = AUDIO_DIR / filename
        if not path.exists():
            print(f"  MISSING: {filename}")
            continue

        for label, side, player in [("A", a, player_a), ("B", b, player_b)]:
            print(f"  {name} → Side {label}...", end="", flush=True)
            if duration:
                player.play(side, path, loop=True)
                time.sleep(duration)
                player.stop()
            else:
                player.play(side, path)
                player.wait()
            print(" done")
            time.sleep(0.3)

    print("  Sound check complete.")


def scenario_crossroute_only(a, b, crossroute):
    """Just cross-route, no sound effects."""
    print("\n--- Cross-route only ---")
    print("  Starting cross-route. Talk into the phones.")
    crossroute.start(a, b)
    wait_for_key("  Press any key to stop...")
    crossroute.stop()
    print("  Done.")


# Inline mixer subprocess code — reads mic PCM from stdin, mixes in a music
# file (looping), writes mixed PCM to stdout.  Runs in its own process so
# Python's GIL doesn't interfere with audio subprocess scheduling.
_MIXER_CODE = """
import sys, array, os

MUSIC_VOL = 0.3
CHUNK = 1024 * 4  # period_size * frame_size (2ch * 2bytes)

music_path = sys.argv[1]
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
        max(-32768, min(32767, int(m + v * MUSIC_VOL)))
        for m, v in zip(mic_samples, music_samples)
    ])

    sys.stdout.buffer.write(out.tobytes())
    sys.stdout.buffer.flush()
"""


def scenario_crossroute_music(a, b):
    """Cross-route with background music mixed into the pipeline."""
    from cold_call.audio import RATE, PERIOD, BUFFER, FORMAT, _set_pdeathsig

    music_path = str(AUDIO_DIR / "rain_city_loop.wav")
    print("\n--- Cross-route + background music ---")
    print("  Mixing rain_city_loop.wav into both earpieces.")
    print("  Talk into the phones. Press any key to stop.")

    procs = []
    pairs = sorted([(a, b), (b, a)], key=lambda p: p[0].card)
    for cap, play in pairs:
        rec = subprocess.Popen(
            ["arecord", "-D", f"plughw:{cap.card},0",
             "-c", "2", "-r", str(RATE), "-f", FORMAT, "-t", "raw",
             "--buffer-size", str(BUFFER), "--period-size", str(PERIOD)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            preexec_fn=_set_pdeathsig,
        )
        mixer = subprocess.Popen(
            [sys.executable, "-c", _MIXER_CODE, music_path],
            stdin=rec.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            preexec_fn=_set_pdeathsig,
        )
        rec.stdout.close()
        plr = subprocess.Popen(
            ["aplay", "-D", f"plughw:{play.card},0",
             "-c", "2", "-r", str(RATE), "-f", FORMAT, "-t", "raw",
             "--buffer-size", str(BUFFER), "--period-size", str(PERIOD)],
            stdin=mixer.stdout, stderr=subprocess.DEVNULL,
            preexec_fn=_set_pdeathsig,
        )
        mixer.stdout.close()
        procs.extend([rec, mixer, plr])
        print(f"  arecord plughw:{cap.card} | mixer | aplay plughw:{play.card}")

    wait_for_key()

    for p in procs:
        try:
            p.terminate()
        except OSError:
            pass
    for p in procs:
        try:
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except OSError:
                pass
    print("  Done.")


def main():
    print("Discovering hardware...")
    sides = discover_sides()
    a, b = sides[0], sides[1]
    print(f"  Side A: card {a.card} ({a.card_id})")
    print(f"  Side B: card {b.card} ({b.card_id})")

    setup_mixer(a)
    setup_mixer(b)

    player_a = SoundPlayer()
    player_b = SoundPlayer()
    crossroute = CrossRoute()

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        while True:
            print_menu()
            ch = wait_for_key("Pick a scenario: ")

            if ch == "q":
                break
            elif ch == "1":
                scenario_full_call(a, b, player_a, player_b, crossroute, "A")
            elif ch == "2":
                scenario_full_call(a, b, player_a, player_b, crossroute, "B")
            elif ch == "3":
                scenario_early_pickup(a, b, player_a, player_b, crossroute, "dial_tone")
            elif ch == "4":
                scenario_early_pickup(a, b, player_a, player_b, crossroute, "dtmf")
            elif ch == "5":
                scenario_no_answer(a, b, player_a, player_b)
            elif ch == "6":
                scenario_caller_abandons(a, b, player_a, player_b)
            elif ch == "7":
                scenario_sound_check(a, b, player_a, player_b)
            elif ch == "8":
                scenario_crossroute_only(a, b, crossroute)
            elif ch == "9":
                scenario_crossroute_music(a, b)
            else:
                print(f"  Unknown option: {ch!r}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        player_a.stop()
        player_b.stop()
        crossroute.stop()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("Cleaned up.")


if __name__ == "__main__":
    main()
