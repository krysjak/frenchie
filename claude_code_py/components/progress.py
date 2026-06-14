"""Progress display components for terminal UI.

Provides ProgressBar and Spinner components inspired by the
official Claude Code design system.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager

from rich.console import Console
from rich.progress import (
    Progress as RichProgress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
)


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)


console = Console()


def _safe(s: str, fallback: str) -> str:
    try:
        enc = sys.stdout.encoding or "utf-8"
        s.encode(enc)
        return s
    except Exception:
        return fallback


# ── Spinner ──────────────────────────────────────────────────────────────────

SPINNER_CHARS = [_safe(c, c) for c in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"]
DOTS_SPINNER = [_safe(c, ".") for c in "⠁⠂⠄⡀⢀⠠⠐⠈"]


class Spinner:
    """Animated spinner for async operations."""

    def __init__(self, message: str = "", frames: list[str] | None = None):
        self.message = message
        self.frames = frames or SPINNER_CHARS
        self._frame_index = 0
        self._start_time = 0.0
        self._running = False

    def start(self, message: str = "") -> None:
        """Start the spinner."""
        if message:
            self.message = message
        self._frame_index = 0
        self._start_time = time.time()
        self._running = True

    def stop(self) -> None:
        """Stop the spinner."""
        self._running = False
        # Clear the line
        console.print(" " * 80, end="\r")

    def update(self, message: str = "") -> None:
        """Update the spinner message and advance frame."""
        if message:
            self.message = message
        self._frame_index = (self._frame_index + 1) % len(self.frames)
        elapsed = time.time() - self._start_time
        frame = self.frames[self._frame_index]
        line = f"  [{CLAUDE_DIM}]{frame}[/{CLAUDE_DIM}] [{TEXT_SECONDARY}]{self.message}[/{TEXT_SECONDARY}] [{TEXT_DIM}]{elapsed:.1f}s[/{TEXT_DIM}]"
        console.print(line, end="\r")

    def render(self) -> str:
        """Return the current line as a string without printing."""
        self._frame_index = (self._frame_index + 1) % len(self.frames)
        frame = self.frames[self._frame_index]
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0
        return f"[{CLAUDE_DIM}]{frame}[/{CLAUDE_DIM}] [{TEXT_SECONDARY}]{self.message}[/{TEXT_SECONDARY}] [{TEXT_DIM}]({elapsed:.1f}s)[/{TEXT_DIM}]"


@contextmanager
def spinner_context(message: str = "Working..."):
    """Context manager that shows a spinner during the wrapped operation."""
    spinner = Spinner(message)
    spinner.start()
    try:
        yield spinner
    finally:
        spinner.stop()


# ── ProgressBar ──────────────────────────────────────────────────────────────

class ProgressBar:
    """Custom progress bar with label and percentage.

    Renders as:  ████████░░░  75%  label
    """

    BAR_WIDTH = 20
    FILL_CHAR = _safe("█", "#")
    EMPTY_CHAR = _safe("░", "-")

    def __init__(self, total: float = 100, label: str = "", color: str = CLAUDE_ORANGE):
        self.total = total
        self.current = 0.0
        self.label = label
        self.color = color

    def advance(self, amount: float = 1) -> None:
        """Advance the progress by the given amount."""
        self.current = min(self.current + amount, self.total)
        self._render()

    def set_completed(self, value: float) -> None:
        """Set the completed value directly."""
        self.current = min(value, self.total)
        self._render()

    def _render(self) -> None:
        """Render the progress bar to the console."""
        ratio = self.current / self.total if self.total > 0 else 0
        filled = int(ratio * self.BAR_WIDTH)
        percent = int(ratio * 100)

        bar = (
            f"[{self.color}]{self.FILL_CHAR * filled}[/{self.color}]"
            f"[{TEXT_DIM}]{self.EMPTY_CHAR * (self.BAR_WIDTH - filled)}[/{TEXT_DIM}]"
        )

        line = (
            f"  {bar}  [{ACCENT_CYAN}]{percent:3d}%[/{ACCENT_CYAN}]"
            f"  [{TEXT_SECONDARY}]{self.label}[/{TEXT_SECONDARY}]"
        )
        console.print(line)

    def complete(self, message: str = "") -> None:
        """Mark as complete with optional success message."""
        self.current = self.total
        bar = f"[{ACCENT_GREEN}]{self.FILL_CHAR * self.BAR_WIDTH}[/{ACCENT_GREEN}]"
        line = f"  {bar}  [{ACCENT_GREEN}]100%[/{ACCENT_GREEN}]"
        if message:
            line += f"  [{ACCENT_GREEN}]✔[/{ACCENT_GREEN}] {message}"
        elif self.label:
            line += f"  [{ACCENT_GREEN}]✔[/{ACCENT_GREEN}] {self.label}"
        console.print(line)


# ── Rich-based Progress ──────────────────────────────────────────────────────

def make_progress(description: str = "", transient: bool = True) -> RichProgress:
    """Create a Rich Progress instance configured with our theme."""
    return RichProgress(
        TextColumn(f"[bold {CLAUDE_ORANGE}]{{task.description}}[/bold {CLAUDE_ORANGE}]"),
        BarColumn(complete_style=CLAUDE_ORANGE, finished_style=ACCENT_GREEN, pulse_style=CLAUDE_LIGHT),
        TextColumn(f"[{TEXT_SECONDARY}]{{task.percentage:>3.0f}}%[/{TEXT_SECONDARY}]"),
        TimeRemainingColumn(),
        console=console,
        transient=transient,
        expand=True,
    )


@contextmanager
def progress_context(description: str = "Processing...", total: float = 100):
    """Context manager for progress reporting."""
    progress = make_progress()
    task_id = progress.add_task(description, total=total)
    try:
        yield progress, task_id
    finally:
        progress.stop()
