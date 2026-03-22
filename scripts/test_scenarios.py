#!/usr/bin/env python3
"""Interactive scenario tester for Cold Calls.

Tests each session phase independently so you can isolate audio issues.
Uses keyboard input (A/B to toggle hook, number keys to pick a scenario).

Stop the service first:  sudo systemctl stop cold-call
Run:                     uv run python scripts/test_scenarios.py
"""

from __future__ import annotations

import sys
import termios
import time
import tty
import select

from cold_call.hardware import discover_sides
from cold_call.audio import SoundPlayer, CrossRoute, setup_mixer, AUDIO_DIR
from cold_call.printer import PrinterConnection


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


def _do_connect(a, b, player_a, player_b, crossroute, printers):
    """Shared connection sequence: print → announcement → cross-route.

    Matches the live session flow. Prints finish before any audio starts
    so the DWC2 bus has zero contention during printing.
    """
    import threading
    from cold_call.prompts import pick_one

    # Print prompts (no audio on bus yet)
    if printers:
        prompt_a = pick_one("apathy")
        prompt_b = pick_one("apathy")
        print(f"  Printing prompts...")
        t1 = threading.Thread(target=printers["A"].print_prompt,
                              args=(prompt_a,), kwargs={"theme": "apathy", "dispatch_num": 1},
                              daemon=True)
        t2 = threading.Thread(target=printers["B"].print_prompt,
                              args=(prompt_b,), kwargs={"theme": "apathy", "dispatch_num": 1},
                              daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

    # Announcement after printing
    print("  Connecting...")
    player_a.play(a, AUDIO_DIR / "connecting.wav")
    player_b.play(b, AUDIO_DIR / "connecting.wav")
    player_a.wait()
    player_b.stop()
    time.sleep(0.2)

    # Cross-route
    bg = AUDIO_DIR / "rain_city_loop.wav"
    music = bg if bg.exists() else None
    crossroute.start(a, b, music_path=music)
    print("  CALL CONNECTED — talk!")


def scenario_full_call(a, b, player_a, player_b, crossroute, printers, hangup_side: str):
    """Full call flow. hangup_side determines who hangs up first."""
    other = "B" if hangup_side == "A" else "A"
    sides_state = {"A": False, "B": False}

    print(f"\n--- Full call: A calls B, {hangup_side} hangs up ---")

    # Caller pickup
    wait_for_toggle(sides_state, "A", True)

    print("  Playing dial tone...")
    player_a.play(a, AUDIO_DIR / "dial_tone.wav")
    time.sleep(2.5)
    player_a.stop()

    print("  Dialing...")
    player_a.play(a, AUDIO_DIR / "dtmf_dial.wav")
    player_a.wait()

    print("  Ringing both sides...")
    player_a.play(a, AUDIO_DIR / "ring_long.wav", loop=True)
    player_b.play(b, AUDIO_DIR / "ring_long.wav", loop=True)

    # Wait for B to pick up
    wait_for_toggle(sides_state, "B", True)
    player_a.stop()
    player_b.stop()
    time.sleep(0.2)

    _do_connect(a, b, player_a, player_b, crossroute, printers)

    # Wait for hangup_side to hang up
    wait_for_toggle(sides_state, hangup_side, False)

    print("  Hanging up...")
    crossroute.stop()

    # Play busy tone to the side still off hook
    still_player = player_a if other == "A" else player_b
    still_side = a if other == "A" else b
    print(f"  Side {other} still off hook — playing busy tone (loops until hangup)")
    still_player.play(still_side, AUDIO_DIR / "busy_tone.wav", loop=True)

    # Wait for other side to hang up
    wait_for_toggle(sides_state, other, False)
    still_player.stop()
    print("  Both on hook. Done.")


def scenario_early_pickup(a, b, player_a, player_b, crossroute, printers, during: str):
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

    _do_connect(a, b, player_a, player_b, crossroute, printers)

    print("  Press A or B to hang up.")
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


def scenario_crossroute_music(a, b, crossroute):
    """Cross-route with background music mixed into the pipeline."""
    music_path = AUDIO_DIR / "rain_city_loop.wav"
    print("\n--- Cross-route + background music ---")
    print("  Mixing rain_city_loop.wav into both earpieces.")
    print("  Talk into the phones. Press any key to stop.")

    crossroute.start(a, b, music_path=music_path)
    wait_for_key()
    crossroute.stop()
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

    # Try to connect printers
    printers = {}
    try:
        pa = PrinterConnection(a)
        pa._get()
        printers["A"] = pa
        print(f"  Printer A ({a.printer_dev}) ready")
    except Exception as e:
        print(f"  Printer A not available: {e}")
    try:
        pb = PrinterConnection(b)
        pb._get()
        printers["B"] = pb
        print(f"  Printer B ({b.printer_dev}) ready")
    except Exception as e:
        print(f"  Printer B not available: {e}")

    if not printers:
        printers = None
        print("  No printers — scenarios will skip printing")

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        while True:
            print_menu()
            ch = wait_for_key("Pick a scenario: ")

            if ch == "q":
                break
            elif ch == "1":
                scenario_full_call(a, b, player_a, player_b, crossroute, printers, "A")
            elif ch == "2":
                scenario_full_call(a, b, player_a, player_b, crossroute, printers, "B")
            elif ch == "3":
                scenario_early_pickup(a, b, player_a, player_b, crossroute, printers, "dial_tone")
            elif ch == "4":
                scenario_early_pickup(a, b, player_a, player_b, crossroute, printers, "dtmf")
            elif ch == "5":
                scenario_no_answer(a, b, player_a, player_b)
            elif ch == "6":
                scenario_caller_abandons(a, b, player_a, player_b)
            elif ch == "7":
                scenario_sound_check(a, b, player_a, player_b)
            elif ch == "8":
                scenario_crossroute_only(a, b, crossroute)
            elif ch == "9":
                scenario_crossroute_music(a, b, crossroute)
            else:
                print(f"  Unknown option: {ch!r}")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        player_a.stop()
        player_b.stop()
        crossroute.stop()
        if printers:
            for pc in printers.values():
                pc.close()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("Cleaned up.")


if __name__ == "__main__":
    main()
