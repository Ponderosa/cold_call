"""Tests for cradle state management and callbacks."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_cradle.py: importing cold_call.cradle...")
from cold_call.cradle import CradleBase, create_cradle
_log.info("test_cradle.py: imports complete")


class TestCradleBase:
    def _make_cradle(self):
        cradle = CradleBase()
        cradle._off_hook = {"A": False, "B": False}
        return cradle

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
