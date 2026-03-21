"""Cold Calls — main entry point.

Discovers hardware, sets up cradle detection, and runs the session loop.

Usage:
    uv run python -m cold_call.main              # With GPIO
    uv run python -m cold_call.main --no-gpio    # Keyboard simulation
"""

from __future__ import annotations

import argparse
import signal
import sys

from cold_call.config import load_config
from cold_call.hardware import discover_sides, print_topology
from cold_call.cradle import create_cradle
from cold_call.session import Session


def main():
    parser = argparse.ArgumentParser(description="Cold Calls station controller")
    parser.add_argument("--no-gpio", action="store_true",
                        help="Simulate cradle switches with keyboard (A/B keys)")
    args = parser.parse_args()

    # Load config
    config = load_config()
    print(f"Station: {config.name} (theme: {config.theme})")
    print(f"Printer buzzer ring: {config.printer.buzzer_ring}")
    print(f"Paper alarm: {'enabled' if config.printer.paper_alarm else 'suppressed'}")
    print()

    # Discover hardware
    print("Discovering hardware...")
    print_topology()
    sides = discover_sides()

    if len(sides) < 2:
        sys.exit(f"Need 2 sides, found {len(sides)}")

    print(f"\nSide A: card {sides[0].card} ({sides[0].card_id}) + {sides[0].printer_dev}")
    print(f"Side B: card {sides[1].card} ({sides[1].card_id}) + {sides[1].printer_dev}")

    # Set up cradle detection
    use_gpio = not args.no_gpio
    cradle = create_cradle(use_gpio=use_gpio)
    if not use_gpio:
        print("\n** GPIO disabled — press A or B to toggle phone hook state **")

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
