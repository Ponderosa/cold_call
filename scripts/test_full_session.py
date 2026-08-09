#!/usr/bin/env python3
"""Simulate a full session without GPIO.

Side A = caller (USB-C phone), Side B = receiver (Type-A phone).
Plays the full sequence: dial tone, DTMF, ring, connecting, cross-route, hangup.
"""

import time

from cold_call.hardware import discover_sides
from cold_call.audio import SoundPlayer, CrossRoute, setup_mixer, AUDIO_DIR

RING_DURATION = 10  # seconds to ring before simulated pickup

sides = discover_sides()
a, b = sides[0], sides[1]

print(f"Side A (caller):   card {a.card} ({a.card_id}) — pick up this phone")
print(f"Side B (receiver): card {b.card} ({b.card_id}) — pick up when it rings")
print()

setup_mixer(a)
setup_mixer(b)

player_a = SoundPlayer()
player_b = SoundPlayer()
crossroute = CrossRoute()

# --- CALLER PICKUP ---
print("Side A picks up...")
print("  Playing dial tone (3s)")
player_a.play(a, AUDIO_DIR / "dial_tone.wav")
time.sleep(3)
player_a.stop()

print("  Dialing 867-5309...")
player_a.play(a, AUDIO_DIR / "dtmf_dial.wav")
player_a.wait()

# --- RINGING ---
print(f"  Side B ringing ({RING_DURATION}s)...")
# Caller hears ring in their ear, receiver hears ring in their ear
player_a.play(a, AUDIO_DIR / "ring.wav")
player_b.play(b, AUDIO_DIR / "ring.wav")
time.sleep(RING_DURATION)
player_a.stop()
player_b.stop()

# --- CONNECTING ---
print("  Side B picks up!")
time.sleep(1)  # moment for phone to reach ear
print("  Connecting call...")
# TODO: replace with a proper recorded announcement
player_a.play(a, AUDIO_DIR / "dial_tone.wav")
player_b.play(b, AUDIO_DIR / "dial_tone.wav")
time.sleep(0.5)
player_a.stop()
player_b.stop()
time.sleep(0.3)

# --- CONVERSATION ---
print()
print("  CALL CONNECTED — talk to each other! (10 seconds)")
crossroute.start(a, b)
time.sleep(10)

# --- HANGUP ---
print()
print("  Hanging up...")
crossroute.stop()
player_a.play(a, AUDIO_DIR / "hangup.wav")
player_b.play(b, AUDIO_DIR / "hangup.wav")
time.sleep(0.5)
player_a.stop()
player_b.stop()

print("  Session complete.")
