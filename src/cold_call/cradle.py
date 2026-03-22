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


class CradleBase:
    """Base interface for cradle detection."""

    def __init__(self):
        self._off_hook: dict[str, bool] = {"A": False, "B": False}
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

    def _toggle(self, side: str):
        """Toggle a side's hook state and fire the appropriate callback."""
        was_off = self._off_hook[side]
        self._off_hook[side] = not was_off
        if was_off:
            if self._on_hangup:
                self._on_hangup(side)
        else:
            if self._on_pickup:
                self._on_pickup(side)

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


class KeyboardCradle(CradleBase):
    """Simulate cradle switches with keyboard input (A/B keys)."""

    def __init__(self):
        super().__init__()
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

    def __init__(self):
        super().__init__()
        self._buttons = {}

    def start(self):
        from gpiozero import Button

        for side, pin in self.PINS.items():
            btn = Button(pin, pull_up=True, bounce_time=0.05)
            # On-hook = pressed (switch closed = LOW), Off-hook = released (switch open = HIGH)
            btn.when_released = lambda s=side: self._pickup(s)
            btn.when_pressed = lambda s=side: self._hangup(s)
            self._buttons[side] = btn
            # Read initial state
            self._off_hook[side] = not btn.is_pressed

    def _pickup(self, side: str):
        self._off_hook[side] = True
        if self._on_pickup:
            self._on_pickup(side)

    def _hangup(self, side: str):
        self._off_hook[side] = False
        if self._on_hangup:
            self._on_hangup(side)

    def stop(self):
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

    def __init__(self, sides: list):
        super().__init__()
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


class DemoCradle(CradleBase):
    """Auto-cycles through sessions for headless testing without GPIO."""

    def __init__(self, call_duration: float = 30.0, pause_between: float = 10.0,
                 pickup_delay: float = 5.0):
        super().__init__()
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
            self._off_hook["A"] = True
            if self._on_pickup:
                self._on_pickup("A")

            # Side B picks up after delay
            time.sleep(self._pickup_delay)
            if not self._running:
                return
            print("  [demo] Side B picks up")
            self._off_hook["B"] = True
            if self._on_pickup:
                self._on_pickup("B")

            # Conversation
            time.sleep(self._call_duration)
            if not self._running:
                return

            # Side A hangs up
            print("  [demo] Side A hangs up")
            self._off_hook["A"] = False
            if self._on_hangup:
                self._on_hangup("A")

            # Side B hangs up shortly after
            time.sleep(3)
            if not self._running:
                return
            print("  [demo] Side B hangs up")
            self._off_hook["B"] = False
            if self._on_hangup:
                self._on_hangup("B")

            # Pause before next cycle
            time.sleep(self._pause_between)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


def create_cradle(mode: str = "gpio", sides: list | None = None) -> CradleBase:
    """Factory: create the appropriate cradle implementation.

    Modes: "gpio", "keyboard", "button", "demo"
    The "button" mode requires sides with input_dev populated.
    """
    if mode == "demo":
        return DemoCradle()
    if mode == "gpio":
        return GPIOCradle()
    if mode == "button":
        if not sides:
            raise RuntimeError("Button cradle requires sides with input devices")
        return ButtonCradle(sides)
    if mode == "keyboard":
        return KeyboardCradle()
    raise ValueError(f"Unknown cradle mode: {mode!r}")
