"""Session state machine for Cold Calls.

Manages the lifecycle of one call: idle → caller_pickup → waiting → connecting →
conversation → hangup → idle.
"""

from __future__ import annotations

import random
import threading
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

from cold_call.audio import SoundPlayer, CrossRoute, setup_mixer, AUDIO_DIR
from cold_call.config import StationConfig
from cold_call.cradle import CradleBase
from cold_call.printer import print_prompt, buzzer_ring
from cold_call.prompts import pick_pair

if TYPE_CHECKING:
    from cold_call.hardware import Side

# Famous phone numbers for DTMF dialing fun
FAMOUS_NUMBERS = [
    "8675309",   # Jenny
    "5558132",   # Ghostbusters-ish
    "5550199",   # Classic 555
    "2125551234", # NYC style
    "4258675309", # Area code + Jenny
]


class State(Enum):
    IDLE = auto()
    CALLER_PICKUP = auto()
    WAITING_FOR_ANSWER = auto()
    CONNECTING = auto()
    CONVERSATION = auto()
    HANGUP = auto()
    COOLDOWN = auto()


class Session:
    """Manages one call session between two sides."""

    def __init__(self, sides: list[Side], cradle: CradleBase, config: StationConfig):
        self.sides = sides
        self.cradle = cradle
        self.config = config
        self.state = State.IDLE
        self._caller: Side | None = None
        self._receiver: Side | None = None
        self._caller_label: str | None = None
        self._receiver_label: str | None = None
        self._player_a = SoundPlayer()
        self._player_b = SoundPlayer()
        self._crossroute = CrossRoute()
        self._state_event = threading.Event()
        self._dispatch_count = 0
        self._running = False

        # Wire up cradle callbacks
        self.cradle.on_pickup(self._handle_pickup)
        self.cradle.on_hangup(self._handle_hangup)

    def _handle_pickup(self, side_label: str):
        """Called when a phone is picked up."""
        print(f"  [event] pickup {side_label}, state={self.state.name}")
        if self.state == State.IDLE:
            # First pickup — this side is the caller
            self._caller_label = side_label
            self._receiver_label = "B" if side_label == "A" else "A"
            self._caller = next(s for s in self.sides if s.label == side_label)
            self._receiver = next(s for s in self.sides if s.label == self._receiver_label)
            self._transition(State.CALLER_PICKUP)
        elif self.state == State.WAITING_FOR_ANSWER and side_label == self._receiver_label:
            # Receiver picks up
            self._transition(State.CONNECTING)

    def _handle_hangup(self, side_label: str):
        """Called when a phone is hung up."""
        print(f"  [event] hangup {side_label}, state={self.state.name}")
        if self.state in (State.CALLER_PICKUP, State.WAITING_FOR_ANSWER):
            if side_label == self._caller_label:
                self._transition(State.HANGUP)
        elif self.state in (State.CONNECTING, State.CONVERSATION):
            self._transition(State.HANGUP)

    def _transition(self, new_state: State):
        self.state = new_state
        self._state_event.set()

    def _caller_player(self) -> SoundPlayer:
        return self._player_a if self._caller_label == "A" else self._player_b

    def _receiver_player(self) -> SoundPlayer:
        return self._player_b if self._caller_label == "A" else self._player_a

    def run(self):
        """Main session loop. Runs until stopped."""
        self._running = True

        # Set up mixers
        for side in self.sides:
            setup_mixer(side)

        print("\nCold Calls ready. Waiting for someone to pick up a phone...")
        print("  (Press A or B to simulate picking up / hanging up)\n")

        while self._running:
            self.state = State.IDLE
            self._caller = None
            self._receiver = None
            self._caller_label = None
            self._receiver_label = None
            self._state_event.clear()

            # --- IDLE: wait for pickup ---
            self._state_event.wait()
            if not self._running:
                break

            if self.state != State.CALLER_PICKUP:
                continue

            # --- CALLER PICKUP ---
            print(f"\n--- Side {self._caller_label} picks up! ---")

            # Dial tone
            print("  Playing dial tone...")
            cp = self._caller_player()
            cp.play(self._caller, AUDIO_DIR / "dial_tone.wav")
            if not self._wait_or_interrupted(2.5):
                cp.stop()
                continue
            cp.stop()

            # DTMF dialing
            number = random.choice(FAMOUS_NUMBERS)
            print(f"  Dialing {number}...")
            cp.play(self._caller, AUDIO_DIR / "dtmf_dial.wav")
            cp.wait()

            if self.state == State.HANGUP:
                continue

            # --- WAITING FOR ANSWER ---
            self.state = State.WAITING_FOR_ANSWER
            self._state_event.clear()
            print(f"  Ringing Side {self._receiver_label}...")
            cp = self._caller_player()
            rp = self._receiver_player()
            cp.play(self._caller, AUDIO_DIR / "ring_long.wav", loop=True)
            rp.play(self._receiver, AUDIO_DIR / "ring_long.wav", loop=True)

            # Buzzer ring on receiver's printer (in background thread)
            buzzer_thread = None
            if self.config.printer.buzzer_ring:
                def _buzz_loop():
                    while self.state == State.WAITING_FOR_ANSWER:
                        buzzer_ring(self._receiver, cycles=1)
                        # Gap between ring cycles (buzzer_ring does ~3s internally,
                        # add pause between cycles)
                        for _ in range(20):  # 2s in 0.1s steps, checking state
                            if self.state != State.WAITING_FOR_ANSWER:
                                return
                            time.sleep(0.1)
                buzzer_thread = threading.Thread(target=_buzz_loop, daemon=True)
                buzzer_thread.start()

            # Wait for receiver pickup or timeout
            picked_up = self._state_event.wait(timeout=30)
            cp.stop()
            rp.stop()
            if buzzer_thread:
                buzzer_thread.join(timeout=2)

            if not picked_up or self.state == State.HANGUP:
                print("  No answer or caller hung up.")
                self._do_hangup()
                continue

            # --- CONNECTING ---
            print(f"  Side {self._receiver_label} picks up!")
            time.sleep(1.0)  # moment to get phone to ear
            print("  Connecting call...")

            # Short connecting tone on both
            cp = self._caller_player()
            rp = self._receiver_player()
            cp.play(self._caller, AUDIO_DIR / "dial_tone.wav")
            rp.play(self._receiver, AUDIO_DIR / "dial_tone.wav")
            time.sleep(0.5)
            cp.stop()
            rp.stop()
            time.sleep(0.3)

            # --- CONVERSATION ---
            self.state = State.CONVERSATION
            self._state_event.clear()
            print("  CALL CONNECTED!")

            # Start cross-route
            self._crossroute.start(self._caller, self._receiver)

            # Print prompts (in background threads so they don't block)
            self._dispatch_count += 1
            prompt_a, prompt_b = pick_pair(self.config.theme)
            caller_prompt = prompt_a if self._caller_label == "A" else prompt_b
            receiver_prompt = prompt_b if self._caller_label == "A" else prompt_a
            suppress = not self.config.printer.paper_alarm

            print(f"  Printing prompts...")
            print(f"    Side {self._caller_label}: {caller_prompt[:60]}...")
            print(f"    Side {self._receiver_label}: {receiver_prompt[:60]}...")

            t1 = threading.Thread(
                target=print_prompt,
                args=(self._caller, caller_prompt, self._dispatch_count),
                kwargs={"suppress_alarm": suppress},
                daemon=True,
            )
            t2 = threading.Thread(
                target=print_prompt,
                args=(self._receiver, receiver_prompt, self._dispatch_count),
                kwargs={"suppress_alarm": suppress},
                daemon=True,
            )
            t1.start()
            t2.start()

            # Wait for hangup
            self._state_event.wait()

            # --- HANGUP ---
            self._do_hangup()

    def _do_hangup(self):
        """Clean up after a call ends."""
        print("  Hanging up...")
        self._crossroute.stop()
        self._player_a.play(self.sides[0], AUDIO_DIR / "hangup.wav")
        self._player_b.play(self.sides[1], AUDIO_DIR / "hangup.wav")
        time.sleep(0.5)
        self._player_a.stop()
        self._player_b.stop()
        print("  Cooldown (5s)...")
        time.sleep(5)
        print("\nWaiting for someone to pick up a phone...")

    def _wait_or_interrupted(self, seconds: float) -> bool:
        """Sleep for `seconds`, but return False early if state changed to HANGUP."""
        self._state_event.clear()
        interrupted = self._state_event.wait(timeout=seconds)
        if interrupted and self.state == State.HANGUP:
            return False
        return True

    def stop(self):
        self._running = False
        self._state_event.set()
        self._crossroute.stop()
        self._player_a.stop()
        self._player_b.stop()
