#!/usr/bin/env python3
"""Physical burn-in: print every prompt of every department on a printer.

Companion to tests/test_raster_safety.py. That test proves the raster bytes
are safe; this proves the hardware survives printing them for real — thermal
head, paper feed, and sustained USB writes on the DWC2 bus.

Defaults to one prompt per department — 7 dispatches, about 1.5 metres of
paper. Widen the burst with --limit once that looks right, and only reach
for --all when you are ready for 175 dispatches and ~25 metres per printer.

Usage:
    uv run python scripts/soak_printer.py                 # 1 per department
    uv run python scripts/soak_printer.py --limit 5       # 5 per department
    uv run python scripts/soak_printer.py --all           # full corpus
    uv run python scripts/soak_printer.py --side A        # one side
    uv run python scripts/soak_printer.py --dev /dev/usb/lp0   # bench printer
    uv run python scripts/soak_printer.py --dry-run       # render only, no printing
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from cold_call.hardware import Side, discover_sides
from cold_call.printer import PrinterConnection
from cold_call.receipt import compose_dispatch
from cold_call.prompts import load_prompts

DEPARTMENTS = [
    "apathy",
    "polite_indifference",
    "ambient_belonging",
    "acceptable_proximity",
    "minimal_engagement",
    "conditional_invitations",
    "deferred_enthusiasm",
]

# Rough paper estimate: 203 dots per inch, 25.4mm per inch.
DOTS_PER_MM = 203 / 25.4

# Breather between dispatches so the thermal head is not driven flat out —
# a soak should stress the print path, not cook the head.
PAUSE = 1.0


def _service_is_active() -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "cold-call"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "active"


def _resolve_targets(args) -> list[Side]:
    """Work out which printers to soak."""
    if args.dev:
        # Bench mode: discovery pairs printers to phones by USB bus, so a
        # printer with no phone beside it never appears as a Side at all.
        return [Side(label="dev", card=-1, card_id="manual", printer_dev=args.dev,
                     usb_bus="manual", input_dev=None)]

    sides = [s for s in discover_sides() if s.printer_dev]
    if not sides:
        sys.exit("ERROR: no printers found. Use --dev /dev/usb/lp0 for a bench printer.")

    if args.side:
        want = args.side.upper()
        sides = [s for s in sides if s.label == want]
        if not sides:
            sys.exit(f"ERROR: side '{want}' has no printer.")

    return sides


def _build_worklist(limit: int | None) -> list[tuple[str, str]]:
    work = []
    for theme in DEPARTMENTS:
        prompts = load_prompts(theme)
        if limit:
            prompts = prompts[:limit]
        work.extend((theme, prompt) for prompt in prompts)
    return work


def soak(side: Side, work: list[tuple[str, str]], dry_run: bool) -> int:
    """Print every dispatch on one printer. Returns the failure count."""
    print(f"\n=== Side {side.label}: {side.printer_dev} — {len(work)} dispatches")

    conn = PrinterConnection(side)
    failures = 0
    started = time.monotonic()

    for i, (theme, prompt) in enumerate(work, start=1):
        label = f"[{i}/{len(work)}] {theme}"

        if dry_run:
            # Still compose it — that is where a bad glyph or asset would blow up.
            img = compose_dispatch(prompt, theme=theme, dispatch_num=i)
            print(f"  {label}: {img.width}x{img.height}  {prompt[:48]}")
            continue

        conn.print_prompt(prompt, theme=theme, dispatch_num=i)

        # print_prompt degrades gracefully and swallows the error, dropping the
        # connection on its way out. A closed handle is how we detect trouble.
        if conn._printer is None:
            failures += 1
            print(f"  {label}: FAILED — {prompt[:48]}")
        else:
            print(f"  {label}: ok")

        time.sleep(PAUSE)

    conn.close()

    elapsed = time.monotonic() - started
    verb = "composed" if dry_run else "printed"
    print(f"--- Side {side.label}: {len(work) - failures}/{len(work)} {verb} "
          f"in {elapsed / 60:.1f} min, {failures} failed")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--side", help="A or B (default: every printer found)")
    parser.add_argument("--dev", help="print to this device directly, skipping discovery")
    parser.add_argument("--limit", type=int, metavar="N", default=1,
                        help="prompts per department (default: 1)")
    parser.add_argument("--all", action="store_true",
                        help="the full corpus — 175 dispatches, ~25m of paper per printer")
    parser.add_argument("--dry-run", action="store_true",
                        help="compose every dispatch but print nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation")
    args = parser.parse_args()

    if not args.dry_run and _service_is_active():
        sys.exit(
            "ERROR: cold-call service is running and owns the printers.\n"
            "Stop it first:  sudo systemctl stop cold-call"
        )

    targets = _resolve_targets(args)
    work = _build_worklist(None if args.all else args.limit)
    if not work:
        sys.exit("ERROR: no prompts loaded — check assets/prompts/.")

    # Estimate paper from the real composed heights of a sample.
    sample = [compose_dispatch(p, theme=t, dispatch_num=1) for t, p in work[:7]]
    avg_mm = sum(img.height for img in sample) / len(sample) / DOTS_PER_MM
    per_printer_m = avg_mm * len(work) / 1000

    print(f"Departments: {len(DEPARTMENTS)}   Dispatches per printer: {len(work)}")
    print(f"Printers:    {', '.join(f'{s.label} ({s.printer_dev})' for s in targets)}")
    print(f"Paper:       ~{per_printer_m:.1f} m per printer, "
          f"~{per_printer_m * len(targets):.1f} m total")
    print(f"Runtime:     ~{len(work) * len(targets) * PAUSE / 60:.0f} min plus print time")

    if not args.dry_run and not args.yes:
        print("\nPoint the printers into a bin.")
        if input("Start the soak? [y/N] ").strip().lower() not in ("y", "yes"):
            sys.exit("Aborted.")

    failures = sum(soak(side, work, args.dry_run) for side in targets)

    print()
    if failures:
        sys.exit(f"FAILED: {failures} dispatch(es) did not print.")
    total = len(work) * len(targets)
    if args.dry_run:
        print(f"Dry run complete: {total} dispatches composed, nothing printed.")
    else:
        print(f"Soak complete: {total} dispatches, no failures.")


if __name__ == "__main__":
    main()
