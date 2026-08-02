"""Tests for session state machine transitions."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_session.py: importing stdlib...")
import threading
import time
from unittest.mock import patch, MagicMock, ANY
_log.info("test_session.py: importing cold_call.session (triggers audio + printer)...")
from cold_call.session import Session, State
_log.info("test_session.py: importing cold_call.config...")
from cold_call.config import StationConfig, PromptsConfig, PrinterConfig
_log.info("test_session.py: importing cold_call.cradle...")
from cold_call.cradle import CradleBase
_log.info("test_session.py: imports complete")


def _make_session(sides, printer_enabled=False, hangup_debounce=0):
    """Create a session with mocked audio and printers."""
    config = StationConfig(
        name="test",
        cradle="keyboard",
        cooldown=0.1,
        background_audio="",
        prompts=PromptsConfig(side_a="apathy", side_b="apathy"),
        printer=PrinterConfig(enabled=printer_enabled, buzzer_ring=False),
    )
    cradle = CradleBase(hangup_debounce=hangup_debounce)

    with patch("cold_call.session.SoundPlayer") as MockPlayer, \
         patch("cold_call.session.CrossRoute") as MockRoute, \
         patch("cold_call.session.setup_mixer"), \
         patch("cold_call.session.PrinterConnection"):
        session = Session(sides, cradle, config)
        # Replace players/route with mocks that have the right methods
        session._player_a = MockPlayer()
        session._player_b = MockPlayer()
        session._crossroute = MockRoute()
        # Make wait() return immediately
        session._player_a.wait.return_value = None
        session._player_b.wait.return_value = None

    return session, cradle


class TestStateTransitions:
    def test_initial_state(self, both_sides):
        session, _ = _make_session(both_sides)
        assert session.state == State.IDLE

    def test_pickup_sets_caller(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_pickup("A")
        assert session.state == State.CALLER_PICKUP
        assert session._caller_label == "A"
        assert session._receiver_label == "B"

    def test_pickup_b_first(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_pickup("B")
        assert session._caller_label == "B"
        assert session._receiver_label == "A"

    def test_receiver_pickup_connects(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_pickup("A")  # caller
        session._handle_pickup("B")  # receiver
        assert session.state == State.CONVERSATION

    def test_hangup_during_pickup(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_pickup("A")
        session._handle_hangup("A")
        assert session.state == State.HANGUP

    def test_hangup_during_conversation(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_pickup("A")
        session._handle_pickup("B")
        assert session.state == State.CONVERSATION
        session._handle_hangup("A")
        assert session.state == State.HANGUP

    def test_second_pickup_during_idle_ignored(self, both_sides):
        """Only the first pickup in IDLE starts a call."""
        session, cradle = _make_session(both_sides)
        # Manually set state to something that shouldn't accept pickups
        session.state = State.HANGUP
        session._handle_pickup("A")
        # State shouldn't change
        assert session.state == State.HANGUP

    def test_hangup_in_idle_ignored(self, both_sides):
        session, cradle = _make_session(both_sides)
        session._handle_hangup("A")
        assert session.state == State.IDLE


class TestQuickTapDebounce:
    """The show failure: visitors tap the cradle and lift again on first try."""

    def test_tap_during_call_setup_does_not_end_the_call(self, both_sides):
        session, cradle = _make_session(both_sides, hangup_debounce=0.3)
        cradle._set_hook("A", True)
        assert session.state == State.CALLER_PICKUP

        # Down and back up inside the window — the session must not notice
        cradle._set_hook("A", False)
        cradle._set_hook("A", True)
        time.sleep(0.5)

        assert session.state == State.CALLER_PICKUP
        assert cradle.is_off_hook("A")

    def test_tap_during_conversation_does_not_end_the_call(self, both_sides):
        session, cradle = _make_session(both_sides, hangup_debounce=0.3)
        cradle._set_hook("A", True)
        cradle._set_hook("B", True)
        assert session.state == State.CONVERSATION

        cradle._set_hook("B", False)
        cradle._set_hook("B", True)
        time.sleep(0.5)

        assert session.state == State.CONVERSATION

    def test_real_hangup_still_ends_the_call(self, both_sides):
        session, cradle = _make_session(both_sides, hangup_debounce=0.3)
        cradle._set_hook("A", True)
        cradle._set_hook("A", False)
        time.sleep(0.5)

        assert session.state == State.HANGUP
        assert not cradle.is_off_hook("A")


class TestDoHangup:
    @patch("cold_call.session.time.sleep")
    def test_plays_hangup_click_to_offhook_side(self, mock_sleep, both_sides):
        session, cradle = _make_session(both_sides)
        cradle._off_hook["A"] = False
        cradle._off_hook["B"] = True

        # After cooldown sleep, put B on-hook so the while-loop exits
        def sleep_side_effect(duration):
            cradle._off_hook["B"] = False
        mock_sleep.side_effect = sleep_side_effect

        session._do_hangup()

        # Should play hangup.wav then busy_tone to side B
        calls = session._player_b.play.call_args_list
        assert len(calls) >= 1
        # First call should be hangup.wav
        assert "hangup.wav" in str(calls[0])

    @patch("cold_call.session.time.sleep")
    def test_stops_player_for_onhook_side(self, mock_sleep, both_sides):
        session, cradle = _make_session(both_sides)
        cradle._off_hook["A"] = False
        cradle._off_hook["B"] = False

        session._do_hangup()

        session._player_a.stop.assert_called()
        session._player_b.stop.assert_called()
