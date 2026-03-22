"""Station configuration loader for Cold Calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "station.yaml"


@dataclass
class PromptsConfig:
    side_a: str = "apathy"
    side_b: str = "apathy"


@dataclass
class PrinterConfig:
    enabled: bool = True
    buzzer_ring: bool = True
    paper_alarm: bool = False


@dataclass
class StationConfig:
    name: str = "cold_call"
    cradle: str = "gpio"
    cooldown: float = 1.0
    background_audio: str = ""
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    printer: PrinterConfig = field(default_factory=PrinterConfig)


def load_config(path: Path | None = None) -> StationConfig:
    """Load station config from YAML file."""
    path = path or CONFIG_PATH
    if not path.exists():
        return StationConfig()

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    prompts_data = data.get("prompts", {})
    prompts = PromptsConfig(
        side_a=prompts_data.get("side_a", "apathy"),
        side_b=prompts_data.get("side_b", "apathy"),
    )

    printer_data = data.get("printer", {})
    printer = PrinterConfig(
        enabled=printer_data.get("enabled", True),
        buzzer_ring=printer_data.get("buzzer_ring", True),
        paper_alarm=printer_data.get("paper_alarm", False),
    )

    return StationConfig(
        name=data.get("name", "cold_call"),
        cradle=data.get("cradle", "gpio"),
        cooldown=float(data.get("cooldown", 1.0)),
        background_audio=data.get("background_audio", ""),
        prompts=prompts,
        printer=printer,
    )
