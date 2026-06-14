"""CompanionSprite — Animated ASCII bulldog mascot.

Inspired by the official Claude Code CompanionSprite, rendered entirely
with Rich markup so it works in any terminal without React/Ink.
"""

from __future__ import annotations

import os
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from rich import box


# ── Color palette ───────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)


class SpriteState(Enum):
    """Animation states for the companion sprite."""
    IDLE = "idle"
    THINKING = "thinking"
    WORKING = "working"
    SUCCESS = "success"
    ERROR = "error"
    WAVE = "wave"
    SLEEP = "sleep"


# ── Bulldog ASCII frames ─────────────────────────────────────────────────────
# ASCII logo wordmark "FRENCHIE" with tagline.
# Used instead of a bulldog mascot.

_D = CLAUDE_DIM
_O = CLAUDE_ORANGE
_L = CLAUDE_LIGHT

_FRENCHIE_LOGO = [
    f"  [{_O}]███████╗██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗██╗███████╗[/]",
    f"  [{_O}]██╔════╝██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║██║██╔════╝[/]",
    f"  [{_O}]█████╗  ██████╔╝█████╗  ██╔██╗ ██║██║     ███████║██║█████╗  [/]",
    f"  [{_O}]██╔══╝  ██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║██║██╔══╝  [/]",
    f"  [{_O}]██║     ██║  ██║███████╗██║ ╚████║╚██████╗██║  ██║██║███████╗[/]",
    f"  [{_O}]╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═╝╚══════╝[/]",
    f"",
    f"  [{_D}]            plan • code • test • ship[/]",
]


def _make_logo_frames(lines: list[str]) -> list[list[str]]:
    """Return a single static frame from a list of pre-colored lines."""
    return [lines]


_SPRITES: dict[SpriteState, list[list[str]]] = {
    SpriteState.IDLE: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.THINKING: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.WORKING: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.SUCCESS: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.ERROR: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.WAVE: _make_logo_frames(_FRENCHIE_LOGO),
    SpriteState.SLEEP: _make_logo_frames(_FRENCHIE_LOGO),
}


# ── Tip messages ─────────────────────────────────────────────────────────────
_TIPS = [
    "Use /model to switch between models",
    "Use /provider to change API provider",
    "Use /init to create a FRENCHIE.md",
    "Use /commit to create a git commit",
    "Use /effort to set thinking effort",
    "Use /mcp to manage MCP servers",
    "Try /diff to see your changes",
    "Use /advisor for model recommendations",
    "Run /cost to track session spend",
    "Use /memory to manage memory files",
    "Try /code-review on your changes",
    "Use /compact to trim conversation history",
    "Run /clear to start a fresh session",
    "Use /permissions to manage tool access",
    "Learn more at codebuff.com/docs",
]


@dataclass
class CompanionSprite:
    """Animated companion sprite with speech bubble support."""

    state: SpriteState = SpriteState.IDLE
    frame_index: int = 0
    message: str = ""
    show_tip: bool = False
    tip_interval: float = 120.0  # seconds between tips
    _last_tip_time: float = field(default_factory=time.time)

    def set_state(self, state: SpriteState, message: str = "") -> None:
        """Set the sprite state and optionally display a message."""
        self.state = state
        self.frame_index = 0
        if message:
            self.message = message

    def next_frame(self) -> list[str]:
        """Advance to the next animation frame and return it."""
        frames = _SPRITES.get(self.state, _SPRITES[SpriteState.IDLE])
        self.frame_index = (self.frame_index + 1) % len(frames)
        return frames[self.frame_index]

    def current_frame(self) -> list[str]:
        """Return the current animation frame without advancing."""
        frames = _SPRITES.get(self.state, _SPRITES[SpriteState.IDLE])
        return frames[self.frame_index % len(frames)]

    def render(self, width: int = 20) -> Panel:
        """Render the sprite inside a Rich Panel."""
        frame = self.current_frame()

        # Build sprite lines (parse Rich markup)
        sprite_text = Text.from_markup("\n".join(frame))

        # Add message bubble if present
        lines = [sprite_text]
        if self.message:
            msg_text = Text(f"\n  {self.message}", style=TEXT_SECONDARY)
            lines.append(msg_text)

        # Add tip periodically
        now = time.time()
        if self.show_tip and (now - self._last_tip_time) > self.tip_interval:
            tip = random.choice(_TIPS)
            self._last_tip_time = now
            lines.append(Text(f"\n  {chr(0x1F4A1)} {tip}", style=TEXT_DIM))

        return Panel(
            Group(*lines),
            border_style=CLAUDE_DIM,
            box=box.SIMPLE,
            padding=(0, 0),
            expand=False,
        )


# ── Convenience helpers ──────────────────────────────────────────────────────

_sprite_instance: CompanionSprite | None = None


def get_companion() -> CompanionSprite:
    """Get or create the global companion singleton."""
    global _sprite_instance
    if _sprite_instance is None:
        _sprite_instance = CompanionSprite()
    return _sprite_instance


def render_buddy(state: SpriteState = SpriteState.IDLE, message: str = "") -> Panel:
    """Render the companion sprite in a given state."""
    buddy = get_companion()
    buddy.set_state(state, message)
    return buddy.render()
