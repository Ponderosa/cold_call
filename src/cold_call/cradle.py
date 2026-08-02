"""Cradle switch detection for Cold Calls.

Two modes:
- GPIO mode: reads physical hook switches via gpiozero
- Keyboard mode (--no-gpio): press A/B keys to toggle sides on/off hook

Both modes expose the same interface so the rest of the code doesn't care.
"""

from __future__ import annotations

import subprocess
import struct
import sys
import select
import termios
import tty
import threading
from typing import Callable


# Seconds a handset must stay on the cradle before we believe it's a real
# hangup. Visitors who've never used a landline routinely drop the handset and
# snatch it back up within a second on their first try; without this, that blip
# tears down the call they were in the middle of starting.
HANGUP_DEBOUNCE = 2.0


class CradleBase:
    """Base interface for cradle detection.

    Tracks two states per side: the raw hook-switch reading and the *reported*
    state the session sees. Pickups are reported immediately — responsiveness
    matters when someone lifts a handset. Hangups are held for
    `hangup_debounce` seconds; if the handset comes back off-hook inside that
    window, the pending hangup is cancelled and neither callback fires, so a
    quick tap on the cradle is invisible to the session state machine.

    This is intent-level debounce, distinct from the 50ms electrical
    `bounce_time` on the GPIO buttons.
    """

    def __init__(self, hangup_debounce: float = HANGUP_DEBOUNCE):
        self._hangup_debounce = hangup_debounce
        # What the session sees.
        self._off_hook: dict[str, bool] = {"A": False, "B": False}
        # What the hook switch actually reads right now.
        self._raw_off_hook: dict[str, bool] = {"A": False, "B": False}
        self._pending_hangup: dict[str, threading.Timer] = {}
        # Reentrant: is_off_hook() is called from the session thread while
        # hook events arrive on gpiozero / helper-reader / timer threads.
        self._lock = threading.RLock()
        self._on_pickup: Callable[[str], None] | None = None
        self._on_hangup: Callable[[str], None] | None = None

    def on_pickup(self, callback: Callable[[str], None]):
        """Register callback for when a phone is picked up. Called with side label."""
        self._on_pickup = callback

    def on_hangup(self, callback: Callable[[str], None]):
        """Register callback for when a phone is hung up. Called with side label."""
        self._on_hangup = callback

    def is_off_hook(self, side: str) -> bool:
        return self._off_hook.get(side, False)

    def _set_hook(self, side: str, off_hook: bool):
        """Feed a raw hook-switch reading through the debounce.

        This is the single chokepoint every mode routes through — GPIO edges,
        HID button toggles, keypresses, and the demo loop.
        """
        callback = None
        with self._lock:
            self._raw_off_hook[side] = off_hook

            # Any new reading supersedes a hangup we hadn't committed yet.
            pending = self._pending_hangup.pop(side, None)
            if pending is not None:
                pending.cancel()

            if off_hook:
                if self._off_hook[side]:
                    # Already reported off-hook — this reading just cancelled a
                    # pending hangup. The blip never happened.
                    return
                self._off_hook[side] = True
                callback = self._on_pickup
            else:
                if not self._off_hook[side]:
                    return
                if self._hangup_debounce > 0:
                    timer = threading.Timer(
                        self._hangup_debounce, self._commit_hangup, args=(side,)
                    )
                    timer.daemon = True
                    self._pending_hangup[side] = timer
                    timer.start()
                    return
                self._off_hook[side] = False
                callback = self._on_hangup

        # Fire outside the lock — callbacks run session logic.
        if callback:
            callback(side)

    def _commit_hangup(self, side: str):
        """Debounce window elapsed with the handset still down — real hangup."""
        with self._lock:
            self._pending_hangup.pop(side, None)
            if self._raw_off_hook[side] or not self._off_hook[side]:
                return  # raced with a pickup, or already committed
            self._off_hook[side] = False
            callback = self._on_hangup

        if callback:
            callback(side)

    def _toggle(self, side: str):
        """Flip a side's hook state (button/keyboard modes)."""
        with self._lock:
            new_state = not self._raw_off_hook[side]
        self._set_hook(side, new_state)

    def _cancel_pending(self):
        """Drop any in-flight hangup timers."""
        with self._lock:
            for timer in self._pending_hangup.values():
                timer.cancel()
            self._pending_hangup.clear()

    def start(self):
        raise NotImplementedError

    def stop(self):
        self._cancel_pending()


class KeyboardCradle(CradleBase):
    """Simulate cradle switches with keyboard input (A/B keys)."""

    def __init__(self, hangup_debounce: float = HANGUP_DEBOUNCE):
        super().__init__(hangup_debounce)
        self._running = False
        self._thread: threading.Thread | None = None
        self._old_settings = None

    def start(self):
        self._running = True
        # Try cbreak mode for single-keypress input; fall back to line-buffered
        try:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            self._cbreak = True
        except (termios.error, OSError):
            self._cbreak = False
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        while self._running:
            if self._cbreak:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1).upper()
                    if ch in ("A", "B"):
                        self._toggle(ch)
                        state = "OFF HOOK" if self._off_hook[ch] else "ON HOOK"
                        print(f"\r  [keyboard] Side {ch}: {state}")
            else:
                # Line-buffered fallback (non-TTY): read a line, take first char
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    line = sys.stdin.readline().strip().upper()
                    if line and line[0] in ("A", "B"):
                        self._toggle(line[0])
                        state = "OFF HOOK" if self._off_hook[line[0]] else "ON HOOK"
                        print(f"  [keyboard] Side {line[0]}: {state}")

    def stop(self):
        super().stop()
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            except (termios.error, OSError):
                pass


class GPIOCradle(CradleBase):
    """Read physical hook switches via GPIO."""

    # BCM pin assignments
    PINS = {"A": 17, "B": 27}

    def __init__(self, hangup_debounce: float = HANGUP_DEBOUNCE):
        super().__init__(hangup_debounce)
        self._buttons = {}

    def start(self):
        from gpiozero import Button

        for side, pin in self.PINS.items():
            btn = Button(pin, pull_up=True, bounce_time=0.05)
            # Off-hook = pressed (switch closed = LOW), On-hook = released (switch open = HIGH)
            btn.when_pressed = lambda s=side: self._set_hook(s, True)
            btn.when_released = lambda s=side: self._set_hook(s, False)
            self._buttons[side] = btn
            # Read initial state
            self._off_hook[side] = btn.is_pressed
            self._raw_off_hook[side] = btn.is_pressed

    def stop(self):
        super().stop()
        for btn in self._buttons.values():
            btn.close()
        self._buttons.clear()


class ButtonCradle(CradleBase):
    """Use POP Phone HID button (KEY_PLAYPAUSE) as hook toggle.

    Each POP Phone has a button that sends KEY_PLAYPAUSE (164) as a
    momentary press. A helper subprocess reads raw input events and
    writes button labels to a pipe. This keeps HID reads out of the
    main Python process to avoid interfering with audio subprocesses.
    """

    def __init__(self, sides: list, hangup_debounce: float = HANGUP_DEBOUNCE):
        super().__init__(hangup_debounce)
        self._sides = sides
        self._running = False
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        import subprocess as sp

        self._running = True

        # Build device→label mapping as args for the helper
        dev_args = []
        for side in self._sides:
            if not side.input_dev:
                print(f"  WARNING: Side {side.label} has no input device for button cradle")
                continue
            dev_args.extend([side.label, side.input_dev])
            print(f"  [button] Side {side.label}: listening on {side.input_dev}")

        if not dev_args:
            return

        # Spawn a subprocess that reads HID events and prints labels
        self._proc = sp.Popen(
            [sys.executable, "-c", _BUTTON_HELPER_CODE, *dev_args],
            stdout=sp.PIPE, stderr=sp.DEVNULL,
        )
        self._thread = threading.Thread(target=self._read_output, daemon=True)
        self._thread.start()

    def _read_output(self):
        """Read button labels from the helper subprocess."""
        while self._running and self._proc:
            line = self._proc.stdout.readline()
            if not line:
                break
            label = line.decode().strip()
            if label in ("A", "B"):
                self._toggle(label)
                state = "OFF HOOK" if self._off_hook[label] else "ON HOOK"
                print(f"  [button] Side {label}: {state}")

    def stop(self):
        super().stop()
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._thread:
            self._thread.join(timeout=2)


# Helper script run as a subprocess — reads HID events and prints side labels.
# Runs in its own process so blocking reads don't affect audio subprocess scheduling.
_BUTTON_HELPER_CODE = """
import struct, sys, select, os

EV_KEY = 0x01
KEY_PLAYPAUSE = 164
FMT = 'llHHi'
SIZE = struct.calcsize(FMT)

# Parse args: label1 dev1 label2 dev2 ...
args = sys.argv[1:]
fds = {}
for i in range(0, len(args), 2):
    label, dev = args[i], args[i+1]
    try:
        fd = os.open(dev, os.O_RDONLY)
        fds[fd] = label
    except OSError as e:
        print(f"ERROR: {dev}: {e}", file=sys.stderr)

if not fds:
    sys.exit(1)

while True:
    ready, _, _ = select.select(list(fds.keys()), [], [])
    for fd in ready:
        data = os.read(fd, SIZE)
        if len(data) < SIZE:
            continue
        _s, _u, t, c, v = struct.unpack(FMT, data)
        if t == EV_KEY and c == KEY_PLAYPAUSE and v == 1:
            sys.stdout.write(fds[fd] + '\\n')
            sys.stdout.flush()
"""


class HybridCradle(CradleBase):
    """Combines GPIO hook switches (absolute state) with POP Phone HID buttons (toggle).

    GPIO is authoritative — switch closed = off hook, switch open = on hook.
    POP button press toggles state as a backup/override.
    Either source fires the same pickup/hangup callbacks.
    """

    PINS = {"A": 17, "B": 27}

    def __init__(self, sides: list, hangup_debounce: float = HANGUP_DEBOUNCE):
        super().__init__(hangup_debounce)
        self._sides = sides
        self._buttons = {}
        self._button_proc: subprocess.Popen | None = None
        self._button_thread: threading.Thread | None = None
        self._running = False

    def start(self):
        self._running = True

        # --- GPIO hook switches ---
        from gpiozero import Button

        for side, pin in self.PINS.items():
            btn = Button(pin, pull_up=True, bounce_time=0.05)
            btn.when_pressed = lambda s=side: self._gpio_pickup(s)
            btn.when_released = lambda s=side: self._gpio_hangup(s)
            self._buttons[side] = btn
            self._off_hook[side] = btn.is_pressed
            self._raw_off_hook[side] = btn.is_pressed
            state = "OFF HOOK" if btn.is_pressed else "ON HOOK"
            print(f"  [gpio] Side {side}: pin {pin} → {state}")

        # --- POP Phone HID buttons ---
        dev_args = []
        for side in self._sides:
            if not side.input_dev:
                print(f"  WARNING: Side {side.label} has no input device for button")
                continue
            dev_args.extend([side.label, side.input_dev])
            print(f"  [button] Side {side.label}: listening on {side.input_dev}")

        if dev_args:
            self._button_proc = subprocess.Popen(
                [sys.executable, "-c", _BUTTON_HELPER_CODE, *dev_args],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            self._button_thread = threading.Thread(target=self._read_buttons, daemon=True)
            self._button_thread.start()

    def _gpio_pickup(self, side: str):
        # Logged as the raw switch reading — a reading that only cancels a
        # pending hangup is deliberately invisible to the session.
        print(f"  [gpio] Side {side}: OFF HOOK")
        self._set_hook(side, True)

    def _gpio_hangup(self, side: str):
        print(f"  [gpio] Side {side}: ON HOOK")
        self._set_hook(side, False)

    def _read_buttons(self):
        """Read POP button presses from helper subprocess — toggles state."""
        while self._running and self._button_proc:
            line = self._button_proc.stdout.readline()
            if not line:
                break
            label = line.decode().strip()
            if label in ("A", "B"):
                self._toggle(label)
                state = "OFF HOOK" if self._off_hook[label] else "ON HOOK"
                print(f"  [button] Side {label}: {state}")

    def stop(self):
        super().stop()
        self._running = False
        # Stop GPIO
        for btn in self._buttons.values():
            btn.close()
        self._buttons.clear()
        # Stop button helper
        if self._button_proc:
            try:
                self._button_proc.terminate()
                self._button_proc.wait(timeout=2)
            except Exception:
                try:
                    self._button_proc.kill()
                except Exception:
                    pass
            self._button_proc = None
        if self._button_thread:
            self._button_thread.join(timeout=2)


class DemoCradle(CradleBase):
    """Auto-cycles through sessions for headless testing without GPIO."""

    def __init__(self, call_duration: float = 30.0, pause_between: float = 10.0,
                 pickup_delay: float = 5.0,
                 hangup_debounce: float = HANGUP_DEBOUNCE):
        super().__init__(hangup_debounce)
        self._call_duration = call_duration
        self._pause_between = pause_between
        self._pickup_delay = pickup_delay
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._demo_loop, daemon=True)
        self._thread.start()

    def _demo_loop(self):
        import time
        while self._running:
            # Side A picks up
            time.sleep(2)
            if not self._running:
                return
            print("  [demo] Side A picks up")
            self._set_hook("A", True)

            # Side B picks up after delay
            time.sleep(self._pickup_delay)
            if not self._running:
                return
            print("  [demo] Side B picks up")
            self._set_hook("B", True)

            # Conversation
            time.sleep(self._call_duration)
            if not self._running:
                return

            # Side A hangs up
            print("  [demo] Side A hangs up")
            self._set_hook("A", False)

            # Side B hangs up shortly after
            time.sleep(3)
            if not self._running:
                return
            print("  [demo] Side B hangs up")
            self._set_hook("B", False)

            # Pause before next cycle
            time.sleep(self._pause_between)

    def stop(self):
        super().stop()
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


def create_cradle(mode: str = "gpio", sides: list | None = None,
                  hangup_debounce: float = HANGUP_DEBOUNCE) -> CradleBase:
    """Factory: create the appropriate cradle implementation.

    Modes: "gpio", "keyboard", "button", "hybrid", "demo"
    The "button" and "hybrid" modes require sides with input_dev populated.
    """
    if mode == "demo":
        return DemoCradle(hangup_debounce=hangup_debounce)
    if mode == "gpio":
        return GPIOCradle(hangup_debounce)
    if mode == "button":
        if not sides:
            raise RuntimeError("Button cradle requires sides with input devices")
        return ButtonCradle(sides, hangup_debounce)
    if mode == "hybrid":
        if not sides:
            raise RuntimeError("Hybrid cradle requires sides with input devices")
        return HybridCradle(sides, hangup_debounce)
    if mode == "keyboard":
        return KeyboardCradle(hangup_debounce)
    raise ValueError(f"Unknown cradle mode: {mode!r}")
