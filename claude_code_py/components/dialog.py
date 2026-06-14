"""Dialog components for interactive terminal prompts.

Provides dialog-style permission prompts, confirmations, inputs,
and diff previews — inspired by the official Claude Code dialog system.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich import box
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import HTML


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


CHECK  = _safe("✔", "[ok]")
CROSS  = _safe("✘", "[x]")
WARN   = _safe("⚠", "[!]")
ARROW  = _safe("▸", ">")
BULLET = _safe("·", "-")


def confirm_dialog(
    title: str,
    message: str,
    confirm_label: str = "Yes",
    cancel_label: str = "No",
    warn: bool = False,
) -> bool:
    """Show a yes/no confirmation dialog.

    Returns True if confirmed, False if cancelled.
    """
    border_color = ACCENT_YELLOW if warn else CLAUDE_ORANGE

    panel = Panel(
        Text(message, style=TEXT_SECONDARY),
        title=f"[bold {border_color}]{title}[/bold {border_color}]",
        border_style=border_color,
        box=box.ROUNDED,
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)

    choices = [
        (confirm_label, ""),
        (cancel_label, ""),
    ]

    selected = [0]
    result = [False]

    POINTER = _safe("❯", ">")
    SPACE = "  "

    def get_text():
        lines = []
        for i, (label, desc) in enumerate(choices):
            if i == selected[0]:
                ptr = f'<style fg="ansicyan"><b>{POINTER}</b></style>'
                lbl = f'<style fg="ansibrightwhite"><b>{label}</b></style>'
                dsc = f'  <style fg="ansicyan">{desc}</style>' if desc else ""
                lines.append(HTML(f"{ptr} {lbl}{dsc}\n"))
            else:
                ptr = f'<style fg="ansiblack">{SPACE}</style>'
                lbl = f'<style fg="ansiwhite">{label}</style>'
                dsc = f'  <style fg="ansidarkgray">{desc}</style>' if desc else ""
                lines.append(HTML(f"{ptr} {lbl}{dsc}\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        selected[0] = (selected[0] - 1) % len(choices)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        selected[0] = (selected[0] + 1) % len(choices)

    @kb.add("enter")
    def _enter(event):
        result[0] = selected[0] == 0
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        result[0] = False
        event.app.exit()

    # Number shortcuts (fixed closure)
    for _n in range(1, min(3, len(choices) + 1)):
        @kb.add(str(_n))
        def _handler(event, val=_n):
            result[0] = val == 1
            event.app.exit()

    layout = Layout(
        Window(
            content=FormattedTextControl(get_text, focusable=True),
            always_hide_cursor=True,
        )
    )

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    app.run()
    return result[0]


def permission_dialog(
    tool_name: str,
    tool_input: dict[str, Any],
    description: str,
) -> str:
    """Show a permission dialog with multiple options.

    Returns one of: 'allow_once', 'always_allow', 'deny_once', 'always_deny'
    """
    icon_map = {
        "Bash": "$", "PowerShell": "PS>", "Write": "W", "Edit": "E",
        "Read": "R", "Glob": "G", "Grep": "Gr", "WebFetch": "WF",
    }
    icon = icon_map.get(tool_name, "?")

    # Summary line
    args_str = ""
    if tool_name in ("Bash", "PowerShell"):
        args_str = tool_input.get("command", "")[:80]
    elif tool_name in ("Read", "Write", "Edit", "NotebookEdit"):
        args_str = tool_input.get("file_path", "")[:60]

    border_style = ACCENT_YELLOW
    title_str = f"[bold {border_style}] Permission Required: {icon} {tool_name} [/bold {border_style}]"

    content_lines = [
        Text(description, style=TEXT_SECONDARY),
        Text(""),
        Text(f"  {args_str}", style=TEXT_DIM) if args_str else Text(""),
    ]

    panel = Panel(
        Group(*[c for c in content_lines if c]),
        title=title_str,
        border_style=border_style,
        box=box.HEAVY,
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)

    choices = [
        ("Allow once", ""),
        ("Yes, always", "add rule to always-allow"),
        ("No, deny once", ""),
        ("Always deny", "add rule to always-deny"),
    ]

    selected = [0]
    result = ["deny_once"]
    POINTER = _safe("❯", ">")

    def get_text():
        lines = []
        for i, (label, desc) in enumerate(choices):
            if i == selected[0]:
                ptr = f'<style fg="ansicyan"><b>{POINTER}</b></style>'
                lbl = f'<style fg="ansibrightwhite"><b>{label}</b></style>'
                dsc = f'  <style fg="ansicyan">{desc}</style>' if desc else ""
                lines.append(HTML(f"{ptr} {lbl}{dsc}\n"))
            else:
                lines.append(HTML(
                    f'<style fg="ansiblack">  </style>'
                    f'<style fg="ansiwhite">{label}</style>'
                    f'{"  <style fg=\"ansidarkgray\">" + desc + "</style>" if desc else ""}\n'
                ))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        selected[0] = (selected[0] - 1) % len(choices)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        selected[0] = (selected[0] + 1) % len(choices)

    @kb.add("enter")
    def _enter(event):
        actions = ["allow_once", "always_allow", "deny_once", "always_deny"]
        result[0] = actions[selected[0]]
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        result[0] = "deny_once"
        event.app.exit()

    for _n in range(1, min(5, len(choices) + 1)):
        @kb.add(str(_n))
        def _handler(event, val=_n):
            actions = ["allow_once", "always_allow", "deny_once", "always_deny"]
            if val - 1 < len(actions):
                result[0] = actions[val - 1]
            event.app.exit()

    layout = Layout(
        Window(
            content=FormattedTextControl(get_text, focusable=True),
            always_hide_cursor=True,
        )
    )

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    app.run()
    return result[0]


def input_dialog(
    title: str,
    prompt: str,
    default: str = "",
    password: bool = False,
) -> str | None:
    """Show a text input dialog.

    Returns the entered string, or None if cancelled.
    """
    border_style = CLAUDE_ORANGE
    panel = Panel(
        Text(prompt, style=TEXT_SECONDARY),
        title=f"[bold {border_style}]{title}[/bold {border_style}]",
        border_style=border_style,
        box=box.ROUNDED,
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)

    try:
        value = console.input(
            f"  [{border_style}]{ARROW}[/{border_style}] "
            f"[{TEXT_SECONDARY}]{prompt}[/{TEXT_SECONDARY}] "
            f"[{TEXT_DIM}]({default})[/{TEXT_DIM}]: "
        )
        return value.strip() or default or None
    except (EOFError, KeyboardInterrupt):
        return None


def select_dialog(
    options: list[tuple[str, str]],
    title: str = "",
    selected_index: int = 0,
) -> int | None:
    """Arrow-key select dialog.

    Returns the index of the selected option, or None if cancelled.
    """
    return _arrow_select(options, title, selected_index)


def multi_select_dialog(
    options: list[tuple[str, str]],
    title: str = "",
    selected_indices: list[int] | None = None,
) -> list[int] | None:
    """Multi-select dialog with checkbox toggling.

    Returns list of selected indices, or None if cancelled.
    """
    if selected_indices is None:
        selected_indices = []
    selected_set = set(selected_indices)
    cursor = [0]
    result = [None]

    POINTER = _safe("❯", ">")
    CHECKED = _safe("☑", "[x]")
    UNCHECKED = _safe("☐", "[ ]")

    def get_text():
        lines = []
        if title:
            lines.append(HTML(f"<b>{title}</b>\n"))
        for i, (label, desc) in enumerate(options):
            checked = CHECKED if i in selected_set else UNCHECKED
            pointer = f'<style fg="ansicyan"><b>{POINTER}</b></style>' if i == cursor[0] else '  '
            check = f'<style fg="ansicyan">{checked}</style>'
            lbl = f'<style fg="ansibrightwhite"><b>{label}</b></style>' if i == cursor[0] else f'<style fg="ansiwhite">{label}</style>'
            dsc = f'  <style fg="ansidarkgray">{desc}</style>' if desc else ""
            lines.append(HTML(f"{pointer} {check} {lbl}{dsc}\n"))
        lines.append(HTML('\n<style fg="ansidarkgray">Space: toggle · Enter: confirm · Esc: cancel</style>'))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        cursor[0] = (cursor[0] - 1) % len(options)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        cursor[0] = (cursor[0] + 1) % len(options)

    @kb.add("space")
    def _toggle(event):
        if cursor[0] in selected_set:
            selected_set.discard(cursor[0])
        else:
            selected_set.add(cursor[0])

    @kb.add("enter")
    def _confirm(event):
        result[0] = sorted(selected_set)
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        result[0] = None
        event.app.exit()

    layout = Layout(
        Window(
            content=FormattedTextControl(get_text, focusable=True),
            always_hide_cursor=True,
        )
    )

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    app.run()
    return result[0]


def diff_preview_dialog(
    file_path: str,
    old_content: str,
    new_content: str,
) -> bool:
    """Show a diff preview and ask for confirmation.

    Returns True if confirmed.
    """
    import difflib

    diff_lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    ))

    diff_text = "".join(diff_lines)

    # Count changes
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    summary = f"[{ACCENT_GREEN}]+{added}[/{ACCENT_GREEN}] [{ACCENT_RED}]-{removed}[/{ACCENT_RED}]"

    if len(diff_text) > 2000:
        diff_text = diff_text[:1997] + "..."

    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)

    panel = Panel(
        syntax,
        title=f"[bold {CLAUDE_ORANGE}]Diff Preview: {file_path}[/bold {CLAUDE_ORANGE}]",
        subtitle=summary,
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
    )
    console.print(panel)

    return confirm_dialog("Apply Changes?", "This will modify the file on disk.")


def notification_dialog(
    title: str,
    message: str,
    level: str = "info",
) -> None:
    """Show a notification-style dialog (no input needed)."""
    border_map = {
        "info": CLAUDE_ORANGE,
        "success": ACCENT_GREEN,
        "warning": ACCENT_YELLOW,
        "error": ACCENT_RED,
    }
    icon_map = {
        "info": "i",
        "success": CHECK,
        "warning": WARN,
        "error": CROSS,
    }
    border_color = border_map.get(level, CLAUDE_ORANGE)
    icon = icon_map.get(level, "?")

    panel = Panel(
        Text(message, style=TEXT_SECONDARY),
        title=f"[bold {border_color}]{icon} {title}[/bold {border_color}]",
        border_style=border_color,
        box=box.ROUNDED,
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _arrow_select(
    options: list[tuple[str, str]],
    title: str = "",
    selected_index: int = 0,
) -> int | None:
    """Arrow-key selection with prompt_toolkit. Returns index or None."""
    selected = [selected_index]
    result = [None]

    POINTER = _safe("❯", ">")
    SPACE = "  "

    def get_text():
        lines = []
        if title:
            lines.append(HTML(f"<b>{title}</b>\n"))
        for i, (label, desc) in enumerate(options):
            if i == selected[0]:
                ptr = f'<style fg="ansicyan"><b>{POINTER}</b></style>'
                lbl = f'<style fg="ansibrightwhite"><b>{label}</b></style>'
                dsc = f'  <style fg="ansicyan">{desc}</style>' if desc else ""
                lines.append(HTML(f"{ptr} {lbl}{dsc}\n"))
            else:
                ptr = f'<style fg="ansiblack">{SPACE}</style>'
                lbl = f'<style fg="ansiwhite">{label}</style>'
                dsc = f'  <style fg="ansidarkgray">{desc}</style>' if desc else ""
                lines.append(HTML(f"{ptr} {lbl}{dsc}\n"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        selected[0] = (selected[0] - 1) % len(options)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        selected[0] = (selected[0] + 1) % len(options)

    @kb.add("enter")
    def _enter(event):
        result[0] = selected[0]
        event.app.exit()

    @kb.add("c-c")
    @kb.add("escape")
    def _cancel(event):
        result[0] = None
        event.app.exit()

    for _n in range(1, min(10, len(options) + 1)):
        @kb.add(str(_n))
        def _handler(event, val=_n):
            if val - 1 < len(options):
                result[0] = val - 1
            event.app.exit()

    layout = Layout(
        Window(
            content=FormattedTextControl(get_text, focusable=True),
            always_hide_cursor=True,
        )
    )

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    app.run()
    return result[0]



