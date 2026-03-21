"""Cradle switch detection for Cold Calls.

Two modes:
- GPIO mode: reads physical hook switches via gpiozero
- Keyboard mode (--no-gpio): press A/B keys to toggle sides on/off hook

Both modes expose the same interface so the rest of the code doesn't care.
"""

from __future__ import annotations

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


def create_cradle(use_gpio: bool = True) -> CradleBase:
    """Factory: create the appropriate cradle implementation."""
    if use_gpio:
        return GPIOCradle()
    return KeyboardCradle()
