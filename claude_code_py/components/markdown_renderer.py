"""Enhanced Markdown renderer for terminal output.

Provides rich rendering of Markdown content including tables,
code blocks with syntax highlighting, lists, and headings.
Inspired by the official Claude Code Markdown and MarkdownTable components.
"""

from __future__ import annotations

import re
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table as RichTable
from rich.text import Text
from rich import box
from rich.rule import Rule


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


def render_markdown(text: str) -> None:
    """Render Markdown text to the console with rich formatting."""
    if not text:
        return

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block (```)
        if line.strip().startswith("```"):
            lang = line.strip().strip("`").strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = "\n".join(code_lines)
            try:
                syntax = Syntax(code_text, lang or "text", theme="monokai", line_numbers=True)
                console.print(syntax)
            except Exception:
                panel = Panel(
                    Text(code_text, style=TEXT_SECONDARY),
                    border_style=CLAUDE_DIM,
                    box=box.ROUNDED,
                )
                console.print(panel)
            i += 1
            continue

        # Table detection (line with | and --- separator)
        if "|" in line and i + 1 < len(lines) and re.match(r"^[\s\|:\-]+$", lines[i + 1]):
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            _render_table(table_lines)
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            if level == 1:
                console.print(f"\n[bold {CLAUDE_ORANGE}]{heading_text}[/bold {CLAUDE_ORANGE}]\n")
            elif level == 2:
                console.print(f"\n[bold {CLAUDE_LIGHT}]{heading_text}[/bold {CLAUDE_LIGHT}]")
                console.print(f"[{CLAUDE_DIM}]{'─' * 40}[/{CLAUDE_DIM}]")
            elif level == 3:
                console.print(f"\n[bold {TEXT_PRIMARY}]{heading_text}[/bold {TEXT_PRIMARY}]")
            else:
                console.print(f"\n[bold {TEXT_SECONDARY}]{heading_text}[/bold {TEXT_SECONDARY}]")
            i += 1
            continue

        # Unordered list
        if re.match(r"^[\s]*[-*+]\s+", line):
            content = re.sub(r"^[\s]*[-*+]\s+", "", line)
            console.print(f"  [{ACCENT_CYAN}]•[/] {content}")
            i += 1
            continue

        # Ordered list
        ordered_match = re.match(r"^[\s]*(\d+)\.\s+(.+)$", line)
        if ordered_match:
            num = ordered_match.group(1)
            content = ordered_match.group(2)
            console.print(f"  [{ACCENT_CYAN}]{num}.[/] {content}")
            i += 1
            continue

        # Blockquote
        if line.strip().startswith(">"):
            content = re.sub(r"^>\s?", "", line)
            console.print(f"  [{CLAUDE_DIM}]│[/] {content}")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$", line.strip()) or re.match(r"^\*{3,}$", line.strip()):
            console.print(Rule(style=CLAUDE_DIM))
            i += 1
            continue

        # Inline formatting (bold, italic, code, links)
        if line.strip():
            formatted = _format_inline(line)
            console.print(formatted)

        i += 1


def _format_inline(text: str) -> Text:
    """Apply inline Markdown formatting to a string."""
    result = Text()

    # Split on code spans first
    parts = re.split(r"(`[^`]+`)", text)

    for part in parts:
        if part.startswith("`") and part.endswith("`"):
            # Inline code
            code_text = part[1:-1]
            result.append(code_text, style=f"bold {ACCENT_GREEN}")
        elif "**" in part or "__" in part:
            # Bold
            bold_parts = re.split(r"(\*\*[^*]+\*\*|__[^_]+__)", part)
            for bp in bold_parts:
                if (bp.startswith("**") and bp.endswith("**")) or (bp.startswith("__") and bp.endswith("__")):
                    result.append(bp[2:-2], style="bold")
                else:
                    result.append(bp)
        elif "*" in part or "_" in part:
            # Italic
            italic_parts = re.split(r"(\*[^*]+\*|_[^_]+_)", part)
            for ip in italic_parts:
                if (ip.startswith("*") and ip.endswith("*")) or (ip.startswith("_") and ip.endswith("_")):
                    result.append(ip[1:-1], style="italic")
                else:
                    result.append(ip)
        else:
            result.append(part)

    return result


def _render_table(lines: list[str]) -> None:
    """Render a Markdown table as a Rich Table."""
    if not lines:
        return

    # Parse header row
    header_cells = [c.strip() for c in lines[0].split("|") if c.strip()]

    # Parse alignment from separator row
    alignments: list[str] = []
    if len(lines) > 1:
        sep_cells = lines[1].split("|")
        for cell in sep_cells:
            cell = cell.strip()
            if cell.startswith(":") and cell.endswith(":"):
                alignments.append("center")
            elif cell.endswith(":"):
                alignments.append("right")
            elif cell.startswith(":"):
                alignments.append("left")
            else:
                alignments.append("left")

    # Create table
    table = RichTable(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style=f"bold {CLAUDE_ORANGE}",
        padding=(0, 1),
        collapse_padding=True,
    )

    for col in header_cells:
        table.add_column(col)

    # Data rows
    for row_line in lines[2:]:
        cells = [c.strip() for c in row_line.split("|") if c.strip()]
        if cells:
            table.add_row(*cells)

    console.print(table)


def render_code_block(code: str, language: str = "", title: str = "") -> None:
    """Render a code block with syntax highlighting."""
    if language and language != "text":
        try:
            syntax = Syntax(code, language, theme="monokai", line_numbers=True)
            if title:
                console.print(Panel(
                    syntax,
                    title=f"[bold {CLAUDE_ORANGE}]{title}[/]",
                    border_style=CLAUDE_DIM,
                    box=box.ROUNDED,
                ))
            else:
                console.print(syntax)
            return
        except Exception:
            pass

    # Fallback: plain text
    console.print(Panel(
        Text(code, style=TEXT_SECONDARY),
        title=f"[bold {CLAUDE_ORANGE}]{title}[/]" if title else None,
        border_style=CLAUDE_DIM,
        box=box.ROUNDED,
    ))


def render_diff(diff_text: str) -> None:
    """Render a unified diff with syntax highlighting."""
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)
