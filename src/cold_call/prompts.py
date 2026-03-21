"""Prompt engine for Cold Calls.

Loads prompts from text files in assets/prompts/, one question per line.
Picks two different prompts per session (one per side).
"""

from __future__ import annotations

import random
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "prompts"


def load_prompts(category: str | None = None) -> list[str]:
    """Load prompts from text files. If category given, load only that file."""
    prompts = []

    if category:
        path = PROMPTS_DIR / f"{category}.txt"
        if path.exists():
            prompts = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    else:
        for path in sorted(PROMPTS_DIR.glob("*.txt")):
            prompts.extend(line.strip() for line in path.read_text().splitlines() if line.strip())

    return prompts


def pick_one(category: str | None = None) -> str:
    """Pick a random prompt from a category."""
    prompts = load_prompts(category)
    if not prompts:
        return "Talk to each other."
    return random.choice(prompts)
