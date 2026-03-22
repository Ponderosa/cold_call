"""Tests for prompt loading and selection."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_prompts.py: importing cold_call.prompts...")
from unittest.mock import patch
from cold_call.prompts import load_prompts, pick_one
_log.info("test_prompts.py: imports complete")


def test_load_category(tmp_prompts):
    with patch("cold_call.prompts.PROMPTS_DIR", tmp_prompts):
        prompts = load_prompts("test_category")
    assert prompts == ["Question one?", "Question two?", "Question three?"]


def test_load_empty_category(tmp_prompts):
    with patch("cold_call.prompts.PROMPTS_DIR", tmp_prompts):
        prompts = load_prompts("empty")
    assert prompts == []


def test_load_nonexistent_category(tmp_prompts):
    with patch("cold_call.prompts.PROMPTS_DIR", tmp_prompts):
        prompts = load_prompts("nonexistent")
    assert prompts == []


def test_load_all(tmp_prompts):
    with patch("cold_call.prompts.PROMPTS_DIR", tmp_prompts):
        prompts = load_prompts()
    # empty.txt contributes nothing, test_category.txt contributes 3
    assert len(prompts) == 3


def test_pick_one_from_category(tmp_prompts):
    with patch("cold_call.prompts.PROMPTS_DIR", tmp_prompts):
        prompt = pick_one("test_category")
    assert prompt in ["Question one?", "Question two?", "Question three?"]


def test_pick_one_fallback():
    with patch("cold_call.prompts.load_prompts", return_value=[]):
        prompt = pick_one("nonexistent")
    assert prompt == "Talk to each other."
