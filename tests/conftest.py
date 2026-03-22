"""Shared fixtures for Cold Calls tests."""

import logging
import subprocess
import pytest
from pathlib import Path
from cold_call.hardware import Side

# Crash-proof test logger — writes to a file with immediate flush so we can
# see which test was running when the system crashes.
_LOG_PATH = Path(__file__).parent.parent / "test_crash.log"
_crash_logger = logging.getLogger("cold_call.test_crash")
_crash_logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(_LOG_PATH, mode="w")  # overwrite each run
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_crash_logger.addHandler(_fh)


def pytest_configure(config):
    """Abort test run if cold-call systemd service is active."""
    _crash_logger.info("=== pytest session starting ===")
    _fh.flush()
    result = subprocess.run(
        ["systemctl", "is-active", "cold-call"],
        capture_output=True, text=True,
    )
    if result.stdout.strip() == "active":
        import sys
        print(
            "\n*** cold-call service is running! ***\n"
            "Stop it first:  sudo systemctl stop cold-call\n"
            "Then re-run:    uv run pytest",
            file=sys.stderr,
        )
        raise pytest.UsageError("cold-call service is active — stop it before running tests")


def pytest_collection_modifyitems(items):
    """Log all collected tests before any run."""
    _crash_logger.info("Collected %d tests:", len(items))
    for item in items:
        _crash_logger.info("  %s", item.nodeid)
    _fh.flush()


def pytest_runtest_logstart(nodeid, location):
    """Log immediately before each test starts."""
    _crash_logger.info(">>> STARTING: %s", nodeid)
    _fh.flush()


def pytest_runtest_logfinish(nodeid, location):
    """Log immediately after each test finishes."""
    _crash_logger.info("<<< FINISHED: %s", nodeid)
    _fh.flush()


def pytest_runtest_makereport(item, call):
    """Log the outcome of each test phase (setup/call/teardown)."""
    if call.when == "call":
        if call.excinfo is not None:
            _crash_logger.info("  FAILED: %s — %s", item.nodeid, call.excinfo.typename)
        else:
            _crash_logger.info("  PASSED: %s", item.nodeid)
        _fh.flush()


def pytest_sessionfinish(session, exitstatus):
    _crash_logger.info("=== pytest session finished (exit %s) ===", exitstatus)
    _fh.flush()


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch):
    """Isolate every test from real hardware and dangerous OS side effects.

    Blocks:
    - os.killpg / os.kill: MagicMock().pid.__int__() returns 1, which
      would send signals to process group 1 (init/systemd) and crash the Pi.
    - subprocess.Popen: prevents accidentally spawning aplay/arecord against
      missing hardware. Tests that need Popen must mock it explicitly.
    """
    monkeypatch.setattr("os.killpg", lambda pgid, sig: None)
    monkeypatch.setattr("os.kill", lambda pid, sig: None)

    def _blocked_popen(*args, **kwargs):
        raise RuntimeError(
            f"Test spawned a real subprocess (forgot to mock Popen?): {args[0]!r}"
        )
    monkeypatch.setattr("subprocess.Popen", _blocked_popen)


@pytest.fixture
def side_a():
    return Side(label="A", card=1, card_id="Phone", printer_dev="/dev/usb/lp0",
                usb_bus="fd500000.pcie", input_dev="/dev/input/event0")


@pytest.fixture
def side_b():
    return Side(label="B", card=2, card_id="Phone_1", printer_dev="/dev/usb/lp1",
                usb_bus="fe980000.usb", input_dev="/dev/input/event1")


@pytest.fixture
def both_sides(side_a, side_b):
    return [side_a, side_b]


@pytest.fixture
def tmp_prompts(tmp_path):
    """Create a temporary prompts directory with test files."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "test_category.txt").write_text("Question one?\nQuestion two?\n\nQuestion three?\n")
    (prompts_dir / "empty.txt").write_text("\n\n")
    return prompts_dir
