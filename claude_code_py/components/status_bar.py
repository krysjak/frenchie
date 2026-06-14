"""StatusBar — Compact live status display for the REPL footer.

Shows model, provider, tool count, MCP status, cost, and mode indicators.
Inspired by the official Claude Code statusline component.
"""

from __future__ import annotations

import os
import time
from rich.table import Table
from rich.text import Text


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)


class StatusBar:
    """Live status bar showing key session information."""

    def __init__(
        self,
        model: str = "",
        provider: str = "",
        tool_count: int = 0,
        mcp_connected: int = 0,
        mcp_failed: int = 0,
        cost: float = 0.0,
        effort: str = "high",
        safe_mode: bool = False,
        is_remote: bool = False,
        mode: str = "default",
    ):
        self.model = model
        self.provider = provider
        self.tool_count = tool_count
        self.mcp_connected = mcp_connected
        self.mcp_failed = mcp_failed
        self.cost = cost
        self.effort = effort
        self.safe_mode = safe_mode
        self.is_remote = is_remote
        self.mode = mode
        self._start_time = time.time()
        self.on_update = None

    def update(
        self,
        model: str | None = None,
        provider: str | None = None,
        tool_count: int | None = None,
        mcp_connected: int | None = None,
        mcp_failed: int | None = None,
        cost: float | None = None,
        effort: str | None = None,
        safe_mode: bool | None = None,
        is_remote: bool | None = None,
        mode: str | None = None,
    ) -> None:
        """Update individual fields."""
        if model is not None:
            self.model = model
        if provider is not None:
            self.provider = provider
        if tool_count is not None:
            self.tool_count = tool_count
        if mcp_connected is not None:
            self.mcp_connected = mcp_connected
        if mcp_failed is not None:
            self.mcp_failed = mcp_failed
        if cost is not None:
            self.cost = cost
        if effort is not None:
            self.effort = effort
        if safe_mode is not None:
            self.safe_mode = safe_mode
        if is_remote is not None:
            self.is_remote = is_remote
        if mode is not None:
            self.mode = mode
        if self.on_update:
            self.on_update()

    def render(self) -> Table:
        """Render the status bar as a single-line Rich Table."""
        table = Table(
            box=None,
            show_header=False,
            show_edge=False,
            padding=(0, 2),
            collapse_padding=True,
        )
        table.add_column(no_wrap=True)

        # ── Model ──
        model_label = Text.assemble(
            (f" {chr(0x1F9E0)} ", TEXT_DIM),
            (self.model, CLAUDE_ORANGE),
        )

        # ── Provider ──
        provider_label = ""
        prov_display = self.provider or "unknown"
        if self.provider == "anthropic":
            provider_label = Text.assemble(
                (f" {chr(0x2601)} ", TEXT_DIM),
                ("Anthropic", ACCENT_CYAN),
            )
        else:
            provider_label = Text.assemble(
                (f" {chr(0x1F5A5)} ", TEXT_DIM),
                (prov_display, ACCENT_CYAN),
            )

        # ── Tools ──
        tools_label = Text.assemble(
            (f" {chr(0x1F527)} ", TEXT_DIM),
            (f"{self.tool_count}", ACCENT_GREEN),
            (" tools", TEXT_DIM),
        )

        # ── MCP ──
        mcp_parts = []
        if self.mcp_connected > 0:
            mcp_parts.append(
                Text.assemble(
                    (f" {chr(0x1F310)} ", TEXT_DIM),
                    (f"{self.mcp_connected}", ACCENT_GREEN),
                    (" MCP", TEXT_DIM),
                )
            )
        if self.mcp_failed > 0:
            mcp_parts.append(
                Text.assemble(
                    (f" {chr(0x26A0)} ", ACCENT_YELLOW),
                    (f"{self.mcp_failed}", ACCENT_YELLOW),
                    (" failed", ACCENT_YELLOW),
                )
            )

        # ── Cost ──
        cost_str = f"${self.cost:.4f}" if self.cost > 0 else "$0.00"
        cost_label = Text.assemble(
            (f" {chr(0x1F4B0)} ", TEXT_DIM),
            (cost_str, ACCENT_YELLOW),
        )

        # ── Effort ──
        effort_colors = {"low": TEXT_DIM, "medium": TEXT_SECONDARY, "high": ACCENT_CYAN, "xhigh": ACCENT_YELLOW}
        effort_color = effort_colors.get(self.effort, TEXT_SECONDARY)
        effort_label = Text.assemble(
            (f" {chr(0x26A1)} ", TEXT_DIM),
            (self.effort.upper(), effort_color),
        )

        # ── Mode badges ──
        badges = []
        if self.mode == "plan":
            badges.append(Text(" PLAN ", "bold black on #ff8787"))
        elif self.mode == "auto":
            badges.append(Text(" AUTO ", "bold black on #5fd787"))
        else:
            badges.append(Text(" BUILD ", "bold black on #e5484d"))

        if self.safe_mode:
            badges.append(Text(" SAFE ", ACCENT_YELLOW))
        if self.is_remote:
            badges.append(Text(" REMOTE ", ACCENT_CYAN))

        # ── Session duration ──
        elapsed = time.time() - self._start_time
        dur_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s" if elapsed >= 60 else f"{int(elapsed)}s"
        duration_label = Text.assemble(
            (f" {chr(0x23F1)} ", TEXT_DIM),
            (dur_str, TEXT_DIM),
        )

        # Combine all parts
        parts = [model_label, provider_label, tools_label, effort_label, cost_label, duration_label]
        parts.extend(mcp_parts)
        for badge in badges:
            parts.append(badge)

        line = Text(" ").join(parts)
        table.add_row(line)
        return table


# ── Global singleton ─────────────────────────────────────────────────────────
_status_bar: StatusBar | None = None


def get_status_bar() -> StatusBar:
    global _status_bar
    if _status_bar is None:
        _status_bar = StatusBar()
    return _status_bar
