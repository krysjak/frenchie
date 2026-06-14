"""FuzzyPicker — Interactive fuzzy search dialog for terminals.

Inspired by the official Claude Code FuzzyPicker component,
allows searching through lists with live filtering.
"""

from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import HTML

# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)


@dataclass
class FuzzyItem:
    """An item in the fuzzy picker list."""
    label: str
    value: Any = None
    description: str = ""
    category: str = ""
    icon: str = ""


def _score_item(query: str, item: FuzzyItem) -> float:
    """Score how well an item matches the query (0-1)."""
    if not query:
        return 1.0
    q = query.lower()
    label_lower = item.label.lower()
    desc_lower = item.description.lower()

    # Exact match
    if q == label_lower:
        return 1.0
    # Starts with
    if label_lower.startswith(q):
        return 0.9
    # Contains
    if q in label_lower:
        return 0.7
    # Fuzzy match
    ratio = difflib.SequenceMatcher(None, q, label_lower).ratio()
    if ratio > 0.4:
        return ratio * 0.5
    # Description match
    if q in desc_lower:
        return 0.3
    return 0.0


def fuzzy_filter(query: str, items: list[FuzzyItem], max_results: int = 10) -> list[tuple[float, FuzzyItem]]:
    """Filter and score items against the query."""
    scored = []
    for item in items:
        score = _score_item(query, item)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: (-x[0], x[1].label))
    return scored[:max_results]


class FuzzyPicker:
    """Interactive fuzzy search picker."""

    def __init__(self, items: list[FuzzyItem], title: str = "Search...", prompt: str = "❯ "):
        self.items = items
        self.title = title
        self.prompt = prompt
        self._result: Any = None
        self._filtered: list[FuzzyItem] = items[:10]
        self._selected_index = 0
        self._query = ""

    def _update_filtered(self, query: str) -> None:
        self._query = query
        scored = fuzzy_filter(query, self.items, max_results=10)
        self._filtered = [item for _, item in scored]
        if self._selected_index >= len(self._filtered):
            self._selected_index = max(0, len(self._filtered) - 1)

    def _get_header(self) -> list:
        """Build the header with title and results count."""
        total = len(self.items)
        shown = len(self._filtered)
        return [
            HTML(f'<style fg="{CLAUDE_ORANGE}"><b>{self.title}</b></style>'),
            HTML(f'  <style fg="{TEXT_DIM}">({shown}/{total})</style>\n\n'),
        ]

    def _get_results(self) -> list:
        """Build the filtered results list."""
        lines = []
        for i, item in enumerate(self._filtered):
            pointer = f'<style fg="{ACCENT_CYAN}"><b>❯</b></style>' if i == self._selected_index else " "
            icon_str = f"<b>{item.icon}</b> " if item.icon else ""
            label = f'<style fg="ansibrightwhite"><b>{item.label}</b></style>' if i == self._selected_index else f'<style fg="ansiwhite">{item.label}</style>'
            desc = f'  <style fg="{TEXT_DIM}">{item.description[:40]}</style>' if item.description and i == self._selected_index else ""
            cat = f'<style fg="{CLAUDE_DIM}">[{item.category}]</style> ' if item.category else ""
            lines.append(HTML(f"{pointer} {icon_str}{cat}{label}{desc}\n"))
        return lines

    def _get_footer(self) -> list:
        """Build the footer with keyboard hints."""
        return [
            HTML(f'\n<style fg="{TEXT_DIM}">↑↓ navigate · Enter select · Esc cancel · Type to filter</style>'),
        ]

    def run(self) -> Any | None:
        """Run the picker and return the selected value, or None."""
        self._update_filtered("")

        search_buffer = Buffer()

        def on_buffer_changed(_buf):
            self._update_filtered(_buf.text)

        search_buffer.on_text_changed += on_buffer_changed

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _up(event):
            if self._filtered:
                self._selected_index = (self._selected_index - 1) % len(self._filtered)

        @kb.add("down")
        @kb.add("j")
        def _down(event):
            if self._filtered:
                self._selected_index = (self._selected_index + 1) % len(self._filtered)

        @kb.add("enter")
        def _enter(event):
            if self._filtered and self._selected_index < len(self._filtered):
                self._result = self._filtered[self._selected_index].value
            event.app.exit()

        @kb.add("c-c")
        @kb.add("escape")
        def _cancel(event):
            self._result = None
            event.app.exit()

        @kb.add("c-n")
        def _next(event):
            if self._filtered:
                self._selected_index = (self._selected_index + 1) % len(self._filtered)

        @kb.add("c-p")
        def _prev(event):
            if self._filtered:
                self._selected_index = (self._selected_index - 1) % len(self._filtered)

        # Build the layout
        def get_search_text():
            header = self._get_header()
            results = self._get_results()
            footer = self._get_footer()
            return header + results + footer

        body = Window(
            content=FormattedTextControl(get_search_text, focusable=True),
            always_hide_cursor=True,
        )

        search_input = Window(
            content=BufferControl(buffer=search_buffer, focusable=True),
            height=1,
            style=f"fg:{TEXT_PRIMARY} bg:{CLAUDE_DIM}",
        )

        layout = Layout(
            HSplit([
                search_input,
                body,
            ])
        )

        app: Application = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
        )
        app.run()
        return self._result


def fuzzy_picker(
    items: list[tuple[str, Any]],
    title: str = "Select...",
    descriptions: list[str] | None = None,
    categories: list[str] | None = None,
    icons: list[str] | None = None,
) -> Any | None:
    """Convenience function to show a fuzzy picker.

    Args:
        items: List of (label, value) tuples.
        title: Dialog title.
        descriptions: Optional list of descriptions matching items.
        categories: Optional list of categories matching items.
        icons: Optional list of icons matching items.

    Returns:
        The selected value, or None if cancelled.
    """
    fuzzy_items = []
    for i, (label, value) in enumerate(items):
        desc = descriptions[i] if descriptions and i < len(descriptions) else ""
        cat = categories[i] if categories and i < len(categories) else ""
        icon = icons[i] if icons and i < len(icons) else ""
        fuzzy_items.append(FuzzyItem(label=label, value=value, description=desc, category=cat, icon=icon))

    picker = FuzzyPicker(fuzzy_items, title=title)
    return picker.run()
