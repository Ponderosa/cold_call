"""Cold Calls — main entry point.

Discovers hardware, sets up cradle detection, and runs the session loop.

Usage:
    uv run python -m cold_call.main                          # Default config
    uv run python -m cold_call.main --config station1.yaml   # Station 1
    uv run python -m cold_call.main --no-gpio                # Keyboard simulation
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys

from cold_call.config import load_config, CONFIG_PATH
from cold_call.hardware import discover_sides, print_topology
from cold_call.cradle import create_cradle
from cold_call.session import Session


def main():
    parser = argparse.ArgumentParser(description="Cold Calls station controller")
    parser.add_argument("--cradle", type=str, default="gpio",
                        choices=["gpio", "keyboard", "button"],
                        help="Cradle detection mode (default: gpio)")
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
    print(f"Station: {config.name}")
    print(f"Cradle: {config.cradle}, cooldown: {config.cooldown}s")
    print(f"Prompts: A={config.prompts.side_a}, B={config.prompts.side_b}")
    print(f"Background audio: {config.background_audio or 'none'}")
    print(f"Printer: {'enabled' if config.printer.enabled else 'disabled'}, "
          f"buzzer: {'on' if config.printer.buzzer_ring else 'off'}")
    print()

    # Discover hardware
    print("Discovering hardware...")
    print_topology()
    sides = discover_sides()

    if len(sides) < 2:
        sys.exit(f"Need 2 sides, found {len(sides)}")

    print(f"\nSide A: card {sides[0].card} ({sides[0].card_id}) + {sides[0].printer_dev}")
    print(f"Side B: card {sides[1].card} ({sides[1].card_id}) + {sides[1].printer_dev}")

    # Set up cradle detection (CLI overrides config)
    if args.demo:
        cradle_mode = "demo"
    elif args.no_gpio:
        cradle_mode = "keyboard"
    elif args.cradle != "gpio":
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
