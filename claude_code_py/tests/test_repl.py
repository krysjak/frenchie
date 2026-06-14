"""Tests for the REPL prompt and helper functions."""

import sys
from unittest.mock import patch
from claude_code_py.repl import (
    _build_prompt,
    _build_simple_logo,
)


def test_build_prompt() -> None:
    """_build_prompt should build prompt string based on mode and terminal width."""
    with patch("shutil.get_terminal_size", return_value=(40, 20)):
        p = _build_prompt("my-project", "default")
        # Should contain a divider line of 40 characters
        assert "─" * 40 in p
        # Should contain build mode prompt indicator
        assert "&gt;" in p

        p_plan = _build_prompt("my-project", "plan")
        assert "Task (plan)" in p_plan

        p_auto = _build_prompt("my-project", "auto")
        assert "Task (auto)" in p_auto


def test_build_simple_logo() -> None:
    """_build_simple_logo should return mascot ASCII/Unicode lines."""
    lines = _build_simple_logo()
    assert isinstance(lines, list)
    assert len(lines) > 0
    assert any("●" in line or "*" in line for line in lines)
