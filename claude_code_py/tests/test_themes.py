"""Tests for the shared themes module."""

from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    BG_SURFACE, BG_ELEVATED,
)


def test_theme_colors_are_hex() -> None:
    """All theme colors should be valid hex color strings."""
    colors = [
        CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
        ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
        TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
        BG_SURFACE, BG_ELEVATED,
    ]
    for color in colors:
        assert color.startswith("#"), f"{color} should start with #"
        assert len(color) == 7, f"{color} should be 7 chars (e.g. #e5484d)"


def test_theme_colors_consistent() -> None:
    """Verify key colors match expectations."""
    assert CLAUDE_ORANGE == "#e5484d", "Brand primary color should match"
    assert ACCENT_GREEN == "#5fd787", "Success color should match"
    assert ACCENT_RED == "#ff5f5f", "Error color should match"


def test_brightness_order() -> None:
    """Text colors should be ordered from brightest to dimmest."""
    # Simple check: hex value should decrease (rough check)
    assert TEXT_PRIMARY > TEXT_SECONDARY, "Primary should be brighter than secondary"
    assert TEXT_SECONDARY > TEXT_DIM, "Secondary should be brighter than dim"
