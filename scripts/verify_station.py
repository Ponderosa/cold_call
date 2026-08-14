#!/usr/bin/env python3
"""Print this station's own corpus on its own printers, then bring it back up.

The deploy check. On a station: ssh in, `git pull`, run this. It stops the
service so the printers are free, prints every prompt each side is configured
to use — ten per side, twenty in all — and restarts the service on the new
code.

Unlike soak_printer.py, which prints all seven departments to prove the
hardware survives the whole corpus, this prints only what *this* station will
actually hand to visitors: side A's department on side A's printer, side B's
on side B's. What comes out of each printer is exactly what that side prints
during a call, so a bad seal, a missing worksheet or a wrapped question shows
up on the paper it will show up on.

The service is restarted in a `finally`, so a crash, a failed print or Ctrl-C
still leaves the station running rather than dark.

Usage:
    uv run python scripts/verify_station.py               # stop, print, restart
    uv run python scripts/verify_station.py --dry-run     # compose only, service untouched
    uv run python scripts/verify_station.py --side A      # one side
    uv run python scripts/verify_station.py --no-restart  # leave the service down
    uv run python scripts/verify_station.py --config station2.yaml
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from cold_call.config import CONFIG_PATH, load_config
from cold_call.hardware import Side, discover_sides
from cold_call.printer import PrinterConnection
from cold_call.prompts import load_prompts
from cold_call.receipt import compose_dispatch

SERVICE = "cold-call"

# Same station identity run-station.sh reads, so this script prints what
# systemd would actually run rather than whatever config/station.yaml holds.
STATION_FILE = Path("/etc/cold-call-station")

# Rough paper estimate: 203 dots per inch, 25.4mm per inch.
DOTS_PER_MM = 203 / 25.4

# Breather between dispatches, matching soak_printer.py — the printers are
# happier fed at a walking pace than driven flat out.
PAUSE = 1.0

# The device nodes are released when the service's process exits, but give
# the bus a moment before we reopen them.
SETTLE = 1.0


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["sudo", "systemctl", *args],
                          capture_output=True, text=True)


def _service_state() -> str:
    """"active", "inactive", "failed", ... or "unknown" if systemd can't say."""
    result = subprocess.run(["systemctl", "is-active", SERVICE],
                            capture_output=True, text=True)
    return result.stdout.strip() or "unknown"


def _resolve_config(args) -> Path:
    """Find the config systemd would use, the way run-station.sh finds it."""
    if args.config:
        return CONFIG_PATH.parent / args.config

    if STATION_FILE.exists():
        station = STATION_FILE.read_text().strip()
        path = CONFIG_PATH.parent / f"station{station}.yaml"
        if not path.exists():
            sys.exit(f"ERROR: {STATION_FILE} says station {station}, "
                     f"but {path} does not exist.")
        return path

    # No station file — fall back to the generic config, same as main.py.
    return CONFIG_PATH


def _build_plan(sides: list[Side], config, want: str | None
                ) -> list[tuple[Side, str, list[str]]]:
    """Pair each side with the department it is configured to print."""
    themes = {"A": config.prompts.side_a, "B": config.prompts.side_b}
    plan = []

    for side in sides:
        if want and side.label != want:
            continue

        theme = themes.get(side.label)
        if theme is None:
            print(f"  WARNING: side {side.label} has no prompts configured — skipping")
            continue

        if side.printer_dev is None:
            print(f"  WARNING: side {side.label} has no printer paired — skipping")
            continue

        prompts = load_prompts(theme)
        if not prompts:
            # Worth stopping for: an empty department means this side would
            # print the "Talk to each other." fallback to every visitor.
            sys.exit(f"ERROR: no prompts loaded for '{theme}' (side {side.label}). "
                     f"Check assets/prompts/{theme}.txt.")

        plan.append((side, theme, prompts))

    return plan


def _print_side(side: Side, theme: str, prompts: list[str], dry_run: bool) -> int:
    """Print one side's whole department. Returns the failure count."""
    print(f"\n=== Side {side.label}: {theme} → {side.printer_dev} "
          f"({len(prompts)} dispatches)")

    conn = PrinterConnection(side)
    failures = 0
    started = time.monotonic()

    for i, prompt in enumerate(prompts, start=1):
        label = f"[{i}/{len(prompts)}]"

        if dry_run:
            # Compose anyway — a bad glyph or a missing seal blows up here.
            img = compose_dispatch(prompt, theme=theme, dispatch_num=i)
            print(f"  {label} {img.width}x{img.height}  {prompt[:52]}")
            continue

        conn.print_prompt(prompt, theme=theme, dispatch_num=i)

        # print_prompt swallows its own errors and drops the connection on the
        # way out, so a closed handle is how a failure surfaces here.
        if conn._printer is None:
            failures += 1
            print(f"  {label} FAILED — {prompt[:52]}")
        else:
            print(f"  {label} ok — {prompt[:52]}")

        time.sleep(PAUSE)

    conn.close()

    elapsed = time.monotonic() - started
    verb = "composed" if dry_run else "printed"
    print(f"--- Side {side.label}: {len(prompts) - failures}/{len(prompts)} {verb} "
          f"in {elapsed / 60:.1f} min, {failures} failed")
    return failures


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--side", help="A or B (default: both)")
    parser.add_argument("--config", help="config file name in config/ "
                                         "(default: from /etc/cold-call-station)")
    parser.add_argument("--dry-run", action="store_true",
                        help="compose every dispatch but print nothing, "
                             "and leave the service alone")
    parser.add_argument("--no-restart", action="store_true",
                        help="leave the service stopped when the print finishes")
    parser.add_argument("--yes", action="store_true",
                        help="skip the confirmation when the station is live")
    args = parser.parse_args()

    config_path = _resolve_config(args)
    config = load_config(config_path)

    try:
        sides = discover_sides()
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}\n"
                 f"Discovery pairs printers to phones by USB bus, so a printer "
                 f"with no phone beside it never appears as a side. For a bench "
                 f"printer use: uv run python scripts/soak_printer.py --dev /dev/usb/lp0")

    want = args.side.upper() if args.side else None
    plan = _build_plan(sides, config, want)
    if not plan:
        sys.exit("ERROR: nothing to print — no side had both a printer and a department.")

    total = sum(len(prompts) for _, _, prompts in plan)

    # Estimate paper from the real composed height of one dispatch per side.
    sample = [compose_dispatch(prompts[0], theme=theme, dispatch_num=1)
              for _, theme, prompts in plan]
    avg_mm = sum(img.height for img in sample) / len(sample) / DOTS_PER_MM

    state = _service_state()

    print(f"Station:  {config.name}  ({config_path.name})")
    print(f"Service:  {SERVICE} is {state}")
    for side, theme, prompts in plan:
        print(f"Side {side.label}:   {theme} — {len(prompts)} prompts → {side.printer_dev}")
    print(f"Paper:    ~{avg_mm * total / 1000:.1f} m total")
    print(f"Runtime:  ~{total * PAUSE / 60:.0f} min plus print time")

    if args.dry_run:
        failures = sum(_print_side(s, t, p, True) for s, t, p in plan)
        print(f"\nDry run complete: {total} dispatches composed, nothing printed.")
        print(f"The {SERVICE} service was not touched.")
        return

    # Only interrupt a live station on purpose — during the festival this
    # command takes the phones down mid-call.
    if state == "active" and not args.yes:
        print(f"\nThis stops {SERVICE}, which is running now.")
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            sys.exit("Aborted — service left running.")

    print(f"\nStopping {SERVICE}...")
    result = _systemctl("stop", SERVICE)
    if result.returncode != 0:
        sys.exit(f"ERROR: could not stop {SERVICE}: {result.stderr.strip()}")
    time.sleep(SETTLE)

    failures = 0
    try:
        for side, theme, prompts in plan:
            failures += _print_side(side, theme, prompts, False)
    finally:
        # However this ends — a dead printer, a traceback, Ctrl-C — the station
        # goes back up. An installation left dark is worse than a failed check.
        if args.no_restart:
            print(f"\nLeaving {SERVICE} stopped (--no-restart). "
                  f"Start it with: sudo systemctl start {SERVICE}")
        else:
            print(f"\nRestarting {SERVICE} on the current code...")
            result = _systemctl("restart", SERVICE)
            if result.returncode != 0:
                print(f"  WARNING: restart failed: {result.stderr.strip()}")
            else:
                time.sleep(SETTLE)
                print(f"  {SERVICE} is {_service_state()}")

    print()
    if failures:
        sys.exit(f"FAILED: {failures} of {total} dispatch(es) did not print.")
    print(f"Verified: {total} dispatches printed across {len(plan)} printer(s), "
          f"no failures.")


if __name__ == "__main__":
    main()
