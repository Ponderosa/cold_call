#!/usr/bin/env python3
"""Render all 6 department receipts as PNG images for preview.

Saves to scripts/output/ — one image per department.

Usage:
    uv run python scripts/render_receipts.py
"""

from pathlib import Path

from cold_call.printer import _compose_dispatch
from cold_call.prompts import pick_one

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

DEPARTMENTS = [
    "polite_indifference",
    "ambient_belonging",
    "acceptable_proximity",
    "minimal_engagement",
    "conditional_invitations",
    "deferred_enthusiasm",
]


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    for i, theme in enumerate(DEPARTMENTS, start=1):
        prompt = pick_one(theme)
        img = _compose_dispatch(prompt, theme=theme, dispatch_num=i)

        out_path = OUTPUT_DIR / f"{theme}.png"
        img.save(str(out_path))
        print(f"  {out_path.name}: {img.width}x{img.height}  —  \"{prompt[:50]}...\"")

    print(f"\nSaved {len(DEPARTMENTS)} receipts to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
