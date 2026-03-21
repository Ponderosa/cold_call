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
from cold_call.printer import PrinterConnection
from cold_call.prompts import pick_one

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
    CONVERSATION = auto()
    HANGUP = auto()


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
        self._music_a = SoundPlayer()
        self._music_b = SoundPlayer()
        self._crossroute = CrossRoute()
        self._state_event = threading.Event()
        self._dispatch_count = 0
        self._running = False

        # Persistent printer connections
        self._printers: dict[str, PrinterConnection] = {
            sides[0].label: PrinterConnection(sides[0]),
            sides[1].label: PrinterConnection(sides[1]),
        }

        # Wire up cradle callbacks
        self.cradle.on_pickup(self._handle_pickup)
        self.cradle.on_hangup(self._handle_hangup)

    def _handle_pickup(self, side_label: str):
        """Called when a phone is picked up."""
        if self.state == State.IDLE:
            # First pickup — this side is the caller
            self._caller_label = side_label
            self._receiver_label = "B" if side_label == "A" else "A"
            self._caller = next(s for s in self.sides if s.label == side_label)
            self._receiver = next(s for s in self.sides if s.label == self._receiver_label)
            self._transition(State.CALLER_PICKUP)
        elif self.state in (State.CALLER_PICKUP, State.WAITING_FOR_ANSWER) \
                and side_label == self._receiver_label:
            # Receiver picks up during any pre-call phase — connect immediately
            self._transition(State.CONVERSATION)

    def _handle_hangup(self, side_label: str):
        """Called when a phone is hung up."""
        if self.state in (State.CALLER_PICKUP, State.WAITING_FOR_ANSWER, State.CONVERSATION):
            self._transition(State.HANGUP)

    def _transition(self, new_state: State):
        self.state = new_state
        self._state_event.set()

    def _player_for(self, side_label: str) -> SoundPlayer:
        return self._player_a if side_label == "A" else self._player_b

    def run(self):
        """Main session loop. Runs until stopped."""
        self._running = True

        # Set up mixers
        for side in self.sides:
            setup_mixer(side)
        if self.config.printer.enabled:
            for pc in self._printers.values():
                try:
                    pc.get()
                    print(f"  Printer {pc.side.label} ({pc.side.printer_dev}) ready")
                except Exception as e:
                    print(f"  WARNING: Printer {pc.side.label} not ready: {e}")
        else:
            print("  Printing disabled")

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

            # Dial tone — interrupted by hangup or early receiver pickup
            print("  Playing dial tone...")
            cp = self._player_for(self._caller_label)
            cp.play(self._caller, AUDIO_DIR / "dial_tone.wav")
            self._wait_or_interrupted(2.5)
            cp.stop()

            if self.state == State.CONVERSATION:
                print(f"  Side {self._receiver_label} already picked up!")
            elif self.state == State.HANGUP:
                self._do_hangup()
                continue
            else:
                # DTMF dialing
                number = random.choice(FAMOUS_NUMBERS)
                print(f"  Dialing {number}...")
                self._state_event.clear()
                cp.play(self._caller, AUDIO_DIR / "dtmf_dial.wav")
                cp.wait()

                if self.state == State.CONVERSATION:
                    print(f"  Side {self._receiver_label} already picked up!")
                elif self.state == State.HANGUP:
                    self._do_hangup()
                    continue
                else:
                    # --- WAITING FOR ANSWER ---
                    self.state = State.WAITING_FOR_ANSWER
                    self._state_event.clear()
                    print(f"  Ringing Side {self._receiver_label}...")
                    cp = self._player_for(self._caller_label)
                    rp = self._player_for(self._receiver_label)
                    cp.play(self._caller, AUDIO_DIR / "ring_long.wav", loop=True)
                    rp.play(self._receiver, AUDIO_DIR / "ring_long.wav", loop=True)

                    # Buzzer ring on receiver's printer
                    buzzer_thread = None
                    if self.config.printer.buzzer_ring:
                        receiver_printer = self._printers[self._receiver_label]
                        def _buzz_loop():
                            while self.state == State.WAITING_FOR_ANSWER:
                                try:
                                    receiver_printer.buzzer_ring(cycles=1)
                                except Exception:
                                    pass
                                for _ in range(20):
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

            # --- CONVERSATION ---
            self._state_event.clear()

            # Start cross-route, then play announcement on top via dmix
            self._crossroute.start(self._caller, self._receiver)
            time.sleep(0.3)

            # Announcement on both earpieces (collect call style)
            cp = self._player_for(self._caller_label)
            rp = self._player_for(self._receiver_label)
            cp.play(self._caller, AUDIO_DIR / "connecting.wav")
            rp.play(self._receiver, AUDIO_DIR / "connecting.wav")
            cp.wait()
            rp.stop()

            # Background music on both earpieces (loops during conversation)
            if self.config.background_audio:
                bg_path = AUDIO_DIR / self.config.background_audio
                self._music_a.play(self.sides[0], bg_path, loop=True)
                self._music_b.play(self.sides[1], bg_path, loop=True)

            print("  CALL CONNECTED!")

            # Print prompts — each side gets its own theme
            self._dispatch_count += 1
            theme_a = self.config.prompts.side_a
            theme_b = self.config.prompts.side_b
            prompt_a = pick_one(theme_a)
            prompt_b = pick_one(theme_b)
            caller_prompt = prompt_a if self._caller_label == "A" else prompt_b
            receiver_prompt = prompt_b if self._caller_label == "A" else prompt_a

            print(f"  Prompts:")
            print(f"    Side {self._caller_label}: {caller_prompt[:60]}...")
            print(f"    Side {self._receiver_label}: {receiver_prompt[:60]}...")

            if self.config.printer.enabled:
                caller_printer = self._printers[self._caller_label]
                receiver_printer = self._printers[self._receiver_label]

                t1 = threading.Thread(
                    target=caller_printer.print_prompt,
                    args=(caller_prompt, self._dispatch_count),
                    daemon=True,
                )
                t2 = threading.Thread(
                    target=receiver_printer.print_prompt,
                    args=(receiver_prompt, self._dispatch_count),
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
        self._music_a.stop()
        self._music_b.stop()
        self._crossroute.stop()

        # Play busy tone to whichever side is still off hook
        for side_label, player, side in [
            ("A", self._player_a, self.sides[0]),
            ("B", self._player_b, self.sides[1]),
        ]:
            if self.cradle.is_off_hook(side_label):
                print(f"  Side {side_label} still off hook — playing busy tone")
                player.play(side, AUDIO_DIR / "busy_tone.wav")
            else:
                player.stop()

        print("  Cooldown (5s)...")
        time.sleep(5)
        self._player_a.stop()
        self._player_b.stop()
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
        self._music_a.stop()
        self._music_b.stop()
        self._crossroute.stop()
        self._player_a.stop()
        self._player_b.stop()
        for pc in self._printers.values():
            pc.close()
