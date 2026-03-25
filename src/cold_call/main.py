"""Cold Calls — main entry point.

Discovers hardware, sets up cradle detection, and runs the session loop.

Usage:
    uv run python -m cold_call.main                          # Default config
    uv run python -m cold_call.main --config station1.yaml   # Station 1
    uv run python -m cold_call.main --no-gpio                # Keyboard simulation
"""

from __future__ import annotations

import argparse
import platform
import socket
import time
from pathlib import Path
import signal
import sys

from cold_call.config import load_config, CONFIG_PATH
from cold_call.hardware import discover_sides, _find_pop_phones, _find_printers
from cold_call.cradle import create_cradle
from cold_call.session import Session

HARDWARE_TIMEOUT = 180  # seconds to wait for USB devices at boot


def _get_ip() -> str:
    """Get the primary IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _get_uptime() -> str:
    """Get system uptime."""
    try:
        raw = Path("/proc/uptime").read_text().split()[0]
        secs = int(float(raw))
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}h {mins}m {secs}s"
        return f"{mins}m {secs}s"
    except Exception:
        return "unknown"


def _print_banner(config):
    """Print startup banner with system and config info."""
    print("=" * 50)
    print("  COLD CALLS — Bureau of Ambient Belonging")
    print("=" * 50)
    print(f"  Host:       {socket.gethostname()}")
    print(f"  IP:         {_get_ip()}")
    print(f"  Python:     {platform.python_version()}")
    print(f"  Uptime:     {_get_uptime()}")
    print(f"  Station:    {config.name}")
    print(f"  Cradle:     {config.cradle}")
    print(f"  Cooldown:   {config.cooldown}s")
    print(f"  Prompts:    A={config.prompts.side_a}, B={config.prompts.side_b}")
    print(f"  Audio:      {config.background_audio or 'none'}")
    print(f"  Printer:    {'enabled' if config.printer.enabled else 'disabled'}, "
          f"buzzer: {'on' if config.printer.buzzer_ring else 'off'}")
    print("=" * 50)
    print()


def _wait_for_hardware() -> list:
    """Wait for 2 phones and 2 printers to appear, with timeout."""
    deadline = time.monotonic() + HARDWARE_TIMEOUT
    last_phones = last_printers = 0

    while time.monotonic() < deadline:
        phones = _find_pop_phones()
        printers = _find_printers()

        if len(phones) != last_phones or len(printers) != last_printers:
            print(f"  Found {len(phones)} phone(s), {len(printers)} printer(s)...")
            last_phones, last_printers = len(phones), len(printers)

        if len(phones) >= 2 and len(printers) >= 2:
            return discover_sides()

        time.sleep(1)

    # Timeout — try with whatever we have
    remaining = HARDWARE_TIMEOUT
    print(f"  Timed out after {remaining}s waiting for hardware.")
    print(f"  Proceeding with {last_phones} phone(s), {last_printers} printer(s).")
    return discover_sides()


def main():
    parser = argparse.ArgumentParser(description="Cold Calls station controller")
    parser.add_argument("--cradle", type=str, default=None,
                        choices=["gpio", "keyboard", "button", "hybrid"],
                        help="Cradle detection mode (default: from config)")
    parser.add_argument("--no-gpio", action="store_true",
                        help="(deprecated) Alias for --cradle keyboard")
    parser.add_argument("--demo", action="store_true",
                        help="Auto-cycle sessions for headless testing without GPIO")
    parser.add_argument("--config", type=str, default=None,
                        help="Config file name in config/ (e.g. station1.yaml)")
    args = parser.parse_args()

    # Load config
    if args.config:
        config_path = CONFIG_PATH.parent / args.config
    else:
        config_path = None
    config = load_config(config_path)
    _print_banner(config)

    # Wait for USB hardware to enumerate
    print("Waiting for hardware...")
    sides = _wait_for_hardware()

    if len(sides) < 2:
        sys.exit(f"Need 2 sides, found {len(sides)}")

    for s in sides:
        bus_name = "DWC2/USB-C" if "980000" in s.usb_bus else "VL805/Type-A"
        print(f"  Side {s.label}: card {s.card} ({s.card_id}) + {s.printer_dev} [{bus_name}]")

    # Set up cradle detection (CLI overrides config)
    if args.demo:
        cradle_mode = "demo"
    elif args.no_gpio:
        cradle_mode = "keyboard"
    elif args.cradle is not None:
        cradle_mode = args.cradle
    else:
        cradle_mode = config.cradle

    cradle = create_cradle(mode=cradle_mode, sides=sides)
    if cradle_mode == "demo":
        print("\n** Demo mode — auto-cycling sessions **")
    elif cradle_mode == "keyboard":
        print("\n** Keyboard mode — press A or B to toggle phone hook state **")
    elif cradle_mode == "button":
        print("\n** Button mode — press POP Phone button to toggle hook state **")
    elif cradle_mode == "hybrid":
        print("\n** Hybrid mode — GPIO hook switches + POP Phone buttons **")

    cradle.start()

    # Run session loop
    session = Session(sides, cradle, config)

    def shutdown(*_):
        print("\nShutting down...")
        session.stop()
        cradle.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)

    try:
        session.run()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
