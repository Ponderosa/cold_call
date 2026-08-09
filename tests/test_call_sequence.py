"""Characterization tests for the shape of a call.

_run_loop carries the whole call — dial tone through hangup — and until now
nothing tested it. These record the exact ordered sequence of what each side
hears, what prints, and when the cross-route starts, so the loop can be
restructured and the call proven unchanged rather than re-run by hand on the
hardware.

They assert order, not implementation. A refactor that keeps the sequence
keeps these passing; one that reorders the briefing and the print does not.

The flow itself is specified in docs/cold-calls-interaction-flow.pdf.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from cold_call.cradle import CradleBase
from cold_call.config import PrinterConfig, PromptsConfig, StationConfig
from cold_call.session import Session, State


class _Recorder:
    """Records every audible and printed event in the order it happens."""

    def __init__(self):
        self.events: list[str] = []

    def player(self, label: str) -> MagicMock:
        p = MagicMock()

        def play(side, path, loop=False, _label=label):
            self.events.append(f"{_label}: play {path.name}" + (" (loop)" if loop else ""))

        p.play.side_effect = play
        p.wait.return_value = None
        p.stop.side_effect = lambda: None
        return p

    def printer(self, label: str) -> MagicMock:
        pc = MagicMock()
        pc.available = True
        pc.print_prompt.side_effect = (
            lambda *a, _label=label, **k: self.events.append(f"{_label}: PRINT")
        )
        pc.buzzer_ring.side_effect = lambda *a, **k: None
        return pc

    def crossroute(self) -> MagicMock:
        route = MagicMock()
        route.start.side_effect = lambda *a, **k: self.events.append("CROSS-ROUTE START")
        route.stop.side_effect = lambda *a, **k: self.events.append("CROSS-ROUTE STOP")
        return route


def _session(recorder: _Recorder, printers: bool = True):
    config = StationConfig(
        name="test",
        cradle="keyboard",
        cooldown=0.0,
        background_audio="",
        prompts=PromptsConfig(side_a="apathy", side_b="apathy"),
        printer=PrinterConfig(enabled=printers, buzzer_ring=False),
    )
    cradle = CradleBase(hangup_debounce=0)

    with patch("cold_call.session.SoundPlayer"), \
         patch("cold_call.session.CrossRoute"), \
         patch("cold_call.session.setup_mixer"), \
         patch("cold_call.session.PrinterConnection"):
        from cold_call.hardware import Side
        sides = [
            Side(label="A", card=1, card_id="Phone", printer_dev="/dev/null",
                 usb_bus="bus-a", input_dev=None),
            Side(label="B", card=2, card_id="Phone_1", printer_dev="/dev/null",
                 usb_bus="bus-b", input_dev=None),
        ]
        session = Session(sides, cradle, config)

    session._player_a = recorder.player("A")
    session._player_b = recorder.player("B")
    session._crossroute = recorder.crossroute()
    session._printers = {"A": recorder.printer("A"), "B": recorder.printer("B")}
    return session


def _run_one_call(session, script):
    """Drive one lap of _run_loop, answering each wait from `script`.

    _run_loop blocks on an Event for pickup, answer and hangup. Rather than
    run real timers, each wait pops the next entry: a callable to fire first
    (a pickup, a hangup) and what the wait should report.
    """
    steps = list(script)

    def fake_wait(timeout=None):
        if not steps:
            session._running = False
            return False
        action, result = steps.pop(0)
        if action:
            action()
        return result

    session._state_event.wait = fake_wait
    session._running = True

    with patch("cold_call.session.time.sleep"):
        # One lap only — _run_loop is a while loop over calls.
        try:
            session._run_loop()
        except StopIteration:
            pass


@pytest.fixture
def recorder():
    return _Recorder()


def test_answered_call_sequence(recorder):
    """The full flow, in order, when the receiver answers.

    This is the sequence in the flow document: dial tone, dialing, ringback,
    then on answer B is mirrored while A is told both are present, the
    heads-up, the print, the briefing, the operator line, and only then does
    audio open between them.
    """
    session = _session(recorder)

    def pickup_a():
        session._handle_pickup("A")

    def pickup_b():
        session._handle_pickup("B")

    _run_one_call(session, [
        (pickup_a, True),    # idle -> caller picks up
        (None, False),       # dial tone window, nobody interrupts
        (pickup_b, True),    # receiver answers during the ring
        (None, False),       # mirrored dial tone window
        (None, True),        # hangup ends the conversation
    ])

    assert recorder.events == [
        "A: play dial_tone.wav",
        "A: play dtmf_dial.wav",
        "A: play ring.wav (loop)",
        "A: play both_present.wav",
        "B: play dial_tone.wav",
        "B: play dtmf_dial.wav",
        "A: play printing_questionnaire.wav",
        "B: play printing_questionnaire.wav",
        "A: PRINT",
        "B: PRINT",
        "A: play briefing.wav",
        "B: play briefing.wav",
        "A: play connecting.wav",
        "B: play connecting.wav",
        "CROSS-ROUTE START",
        "CROSS-ROUTE STOP",
    ]


def test_answered_during_the_hold(recorder):
    """Answering late is the same call, with the hold bed in front of it.

    The receiver has no reason to hurry — nothing is ringing at them except a
    printer — so this is at least as likely as answering during the ring.
    """
    session = _session(recorder)

    _run_one_call(session, [
        (lambda: session._handle_pickup("A"), True),
        (None, False),       # dial tone window
        (None, False),       # ring window expires, hold begins
        (lambda: session._handle_pickup("B"), True),
        (None, False),
        (None, True),
    ])

    assert recorder.events[:5] == [
        "A: play dial_tone.wav",
        "A: play dtmf_dial.wav",
        "A: play ring.wav (loop)",
        "A: play hold.wav",
        "A: play both_present.wav",
    ]
    assert recorder.events[-1] == "CROSS-ROUTE STOP"
    assert "CROSS-ROUTE START" in recorder.events


def test_nothing_is_audible_while_the_printers_run(recorder):
    """The phones and printers share a USB controller — audio never overlaps.

    Guards the ordering rule rather than the sequence: whatever else moves,
    no clip may start between the two prints.
    """
    session = _session(recorder)

    _run_one_call(session, [
        (lambda: session._handle_pickup("A"), True),
        (None, False),
        (lambda: session._handle_pickup("B"), True),
        (None, False),
        (None, True),
    ])

    first = recorder.events.index("A: PRINT")
    last = max(i for i, e in enumerate(recorder.events) if e.endswith("PRINT"))
    between = recorder.events[first:last + 1]
    assert all(e.endswith("PRINT") for e in between), (
        f"audio played while the printers were running: {between}"
    )


def test_briefing_lands_after_the_print(recorder):
    """The paper is in their hands while the voice explains what to do with it.

    This is the one ordering the questionnaire branch had the other way
    round, and it is the reason the receipt can carry a consolidated
    procedure instead of steps threaded around the question.
    """
    session = _session(recorder)

    _run_one_call(session, [
        (lambda: session._handle_pickup("A"), True),
        (None, False),
        (lambda: session._handle_pickup("B"), True),
        (None, False),
        (None, True),
    ])

    assert (recorder.events.index("A: play briefing.wav")
            > recorder.events.index("A: PRINT"))


def test_no_answer_sequence(recorder):
    """Nobody picks up: two rings, the hold bed, then the intercept.

    The hold asset plays once and fades — a second hold pass here would mean
    the window and the file had drifted apart.
    """
    session = _session(recorder)

    _run_one_call(session, [
        (lambda: session._handle_pickup("A"), True),
        (None, False),       # dial tone window
        (None, False),       # ring window expires
        (None, False),       # hold window expires
    ])

    assert recorder.events == [
        "A: play dial_tone.wav",
        "A: play dtmf_dial.wav",
        "A: play ring.wav (loop)",
        "A: play hold.wav",
        "A: play not_in_service.wav",
        "CROSS-ROUTE STOP",
    ]


def test_caller_hangs_up_during_the_ring(recorder):
    """Abort paths matter as much as the happy one — nothing prints."""
    session = _session(recorder)

    def hang_up():
        session._handle_pickup("A")
        session._handle_hangup("A")

    _run_one_call(session, [
        (lambda: session._handle_pickup("A"), True),
        (None, False),
        (hang_up, True),     # caller hangs up rather than the receiver answering
    ])

    assert "A: PRINT" not in recorder.events
    assert "CROSS-ROUTE START" not in recorder.events
