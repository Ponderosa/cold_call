"""Tests for cradle state management and callbacks."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_cradle.py: importing cold_call.cradle...")
import time
from cold_call.cradle import CradleBase, create_cradle
_log.info("test_cradle.py: imports complete")


class TestCradleBase:
    def _make_cradle(self):
        """Cradle with debounce off — tests the raw state/callback contract."""
        return CradleBase(hangup_debounce=0)

    def test_initial_state(self):
        cradle = self._make_cradle()
        assert not cradle.is_off_hook("A")
        assert not cradle.is_off_hook("B")

    def test_toggle_pickup(self):
        cradle = self._make_cradle()
        pickups = []
        cradle.on_pickup(lambda side: pickups.append(side))

        cradle._toggle("A")
        assert cradle.is_off_hook("A")
        assert pickups == ["A"]

    def test_toggle_hangup(self):
        cradle = self._make_cradle()
        hangups = []
        cradle.on_hangup(lambda side: hangups.append(side))

        # Pick up then hang up
        cradle._toggle("A")
        cradle._toggle("A")
        assert not cradle.is_off_hook("A")
        assert hangups == ["A"]

    def test_toggle_independent_sides(self):
        cradle = self._make_cradle()
        cradle._toggle("A")
        cradle._toggle("B")
        assert cradle.is_off_hook("A")
        assert cradle.is_off_hook("B")

        cradle._toggle("A")
        assert not cradle.is_off_hook("A")
        assert cradle.is_off_hook("B")

    def test_no_callback_doesnt_crash(self):
        cradle = self._make_cradle()
        # No callbacks registered — should not raise
        cradle._toggle("A")
        cradle._toggle("A")

    def test_callback_sequence(self):
        cradle = self._make_cradle()
        events = []
        cradle.on_pickup(lambda s: events.append(("pickup", s)))
        cradle.on_hangup(lambda s: events.append(("hangup", s)))

        cradle._toggle("A")  # pickup
        cradle._toggle("B")  # pickup
        cradle._toggle("A")  # hangup
        cradle._toggle("B")  # hangup

        assert events == [
            ("pickup", "A"),
            ("pickup", "B"),
            ("hangup", "A"),
            ("hangup", "B"),
        ]


class TestHangupDebounce:
    """A quick tap on the cradle must be invisible to the session.

    Visitors unfamiliar with landlines drop the handset and snatch it back up
    within a second on their first try; that blip used to tear down the call
    they were in the middle of starting.
    """

    def _make_cradle(self, debounce=0.15):
        cradle = CradleBase(hangup_debounce=debounce)
        events = []
        cradle.on_pickup(lambda s: events.append(("pickup", s)))
        cradle.on_hangup(lambda s: events.append(("hangup", s)))
        return cradle, events

    def test_hangup_is_not_reported_immediately(self):
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        cradle._set_hook("A", False)

        # Still inside the debounce window — session must not see a hangup yet
        assert events == [("pickup", "A")]
        assert cradle.is_off_hook("A")

    def test_hangup_commits_after_window(self):
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        cradle._set_hook("A", False)
        time.sleep(0.3)

        assert events == [("pickup", "A"), ("hangup", "A")]
        assert not cradle.is_off_hook("A")

    def test_quick_tap_fires_nothing(self):
        """Down and back up inside the window: no hangup, no second pickup."""
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        events.clear()

        cradle._set_hook("A", False)
        cradle._set_hook("A", True)
        time.sleep(0.3)

        assert events == []
        assert cradle.is_off_hook("A")

    def test_repeated_taps_still_fire_nothing(self):
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        events.clear()

        for _ in range(4):
            cradle._set_hook("A", False)
            cradle._set_hook("A", True)
        time.sleep(0.3)

        assert events == []
        assert cradle.is_off_hook("A")

    def test_tap_then_genuine_hangup(self):
        """After a cancelled blip, a real hangup still lands."""
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        events.clear()

        cradle._set_hook("A", False)
        cradle._set_hook("A", True)   # blip cancelled
        cradle._set_hook("A", False)  # for real this time
        time.sleep(0.3)

        assert events == [("hangup", "A")]
        assert not cradle.is_off_hook("A")

    def test_pickup_is_never_delayed(self):
        cradle, events = self._make_cradle(debounce=5.0)
        cradle._set_hook("A", True)
        assert events == [("pickup", "A")]

    def test_debounce_is_per_side(self):
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        cradle._set_hook("B", True)
        events.clear()

        cradle._set_hook("A", False)
        cradle._set_hook("A", True)   # A blips
        cradle._set_hook("B", False)  # B really hangs up
        time.sleep(0.3)

        assert events == [("hangup", "B")]
        assert cradle.is_off_hook("A")
        assert not cradle.is_off_hook("B")

    def test_toggle_mode_tap_fires_nothing(self):
        """Button/keyboard modes go through the same debounce."""
        cradle, events = self._make_cradle()
        cradle._toggle("A")  # pickup
        events.clear()

        cradle._toggle("A")  # "hangup" — held
        cradle._toggle("A")  # picked back up inside the window
        time.sleep(0.3)

        assert events == []
        assert cradle.is_off_hook("A")

    def test_stop_cancels_pending_hangup(self):
        cradle, events = self._make_cradle()
        cradle._set_hook("A", True)
        cradle._set_hook("A", False)
        cradle.stop()
        time.sleep(0.3)

        assert events == [("pickup", "A")]


def test_create_cradle_keyboard():
    cradle = create_cradle("keyboard")
    assert hasattr(cradle, "start")
    assert hasattr(cradle, "stop")


def test_create_cradle_demo():
    cradle = create_cradle("demo")
    assert hasattr(cradle, "_demo_loop")


def test_create_cradle_gpio():
    cradle = create_cradle("gpio")
    assert hasattr(cradle, "PINS")


def test_create_cradle_unknown():
    try:
        create_cradle("invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown cradle mode" in str(e)


def test_create_cradle_button_requires_sides():
    try:
        create_cradle("button")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "requires sides" in str(e)
