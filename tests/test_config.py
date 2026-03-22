"""Tests for station config loading."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_config.py: importing cold_call.config...")
from pathlib import Path
from cold_call.config import load_config, StationConfig, PromptsConfig, PrinterConfig
_log.info("test_config.py: imports complete")


def test_defaults_when_no_file(tmp_path):
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config.name == "cold_call"
    assert config.cradle == "gpio"
    assert config.cooldown == 1.0
    assert config.background_audio == ""
    assert config.prompts.side_a == "apathy"
    assert config.prompts.side_b == "apathy"
    assert config.printer.enabled is True
    assert config.printer.buzzer_ring is True


def test_load_full_config(tmp_path):
    cfg = tmp_path / "test.yaml"
    cfg.write_text("""
name: station2
cradle: button
cooldown: 2.5
background_audio: rain.wav

prompts:
  side_a: ambient_belonging
  side_b: polite_indifference

printer:
  enabled: false
  buzzer_ring: false
  paper_alarm: true
""")
    config = load_config(cfg)
    assert config.name == "station2"
    assert config.cradle == "button"
    assert config.cooldown == 2.5
    assert config.background_audio == "rain.wav"
    assert config.prompts.side_a == "ambient_belonging"
    assert config.prompts.side_b == "polite_indifference"
    assert config.printer.enabled is False
    assert config.printer.buzzer_ring is False


def test_partial_config_uses_defaults(tmp_path):
    cfg = tmp_path / "partial.yaml"
    cfg.write_text("name: mystation\n")
    config = load_config(cfg)
    assert config.name == "mystation"
    assert config.cradle == "gpio"
    assert config.prompts.side_a == "apathy"
    assert config.printer.enabled is True


def test_empty_yaml_uses_defaults(tmp_path):
    cfg = tmp_path / "empty.yaml"
    cfg.write_text("")
    config = load_config(cfg)
    assert config.name == "cold_call"
