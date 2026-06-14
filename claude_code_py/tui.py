from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import HTML

from claude_code_py.permissions import PermissionContext, PermissionDecision, PermissionRuleValue

console = Console()

# ── Color Palette (matches repl.py) ─────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)


def _safe(s: str, fallback: str) -> str:
    try:
        enc = sys.stdout.encoding or "utf-8"
        s.encode(enc)
        return s
    except Exception:
        return fallback


ARROW_R = _safe("▸", ">")
CHECK   = _safe("✔", "[ok]")
CROSS   = _safe("✘", "[x]")
WARN    = _safe("⚠", "[!]")
BULLET  = _safe("·", "-")
BLOCK   = _safe("█", "#")
LINE_V  = _safe("│", "|")
SPINNER_FRAMES = [_safe(c, ".") for c in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"]


# ── Tool Icons ───────────────────────────────────────────────────────────────
TOOL_ICONS: dict[str, str] = {
    "Read":         _safe("📖", "[R]"),
    "Write":        _safe("✏", "[W]"),
    "Edit":         _safe("✎", "[E]"),
    "Bash":         _safe("$", "$"),
    "PowerShell":   _safe("PS>", "PS>"),
    "Glob":         _safe("🔍", "[G]"),
    "Grep":         _safe("🔎", "[Gr]"),
    "WebFetch":     _safe("🌐", "[WF]"),
    "WebSearch":    _safe("🔎", "[WS]"),
    "TodoWrite":    _safe("☑", "[T]"),
    "Agent":        _safe("🤖", "[A]"),
    "NotebookEdit": _safe("📓", "[N]"),
}


# ── Tool Description Formatting ──────────────────────────────────────────────
def format_tool_description(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name in ("Read", "Write", "Edit", "NotebookEdit"):
        path = tool_input.get("file_path", tool_input.get("path", ""))
        # Shorten path for display
        parts = str(path).replace("\\", "/").split("/")
        if len(parts) > 3:
            short_path = "/".join(parts[-2:])
        else:
            short_path = str(path)
        return f"{tool_name} {short_path}"
    if tool_name in ("Bash", "PowerShell"):
        cmd = tool_input.get("command", "")
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        return f"{tool_name} {cmd}"
    params = ", ".join(f"{k}={v}" for k, v in tool_input.items())
    if len(params) > 60:
        params = params[:57] + "..."
    return f"{tool_name}({params})" if params else tool_name


def get_permission_rule_content(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name in ("Read", "Write", "Edit", "NotebookEdit"):
        return f"*{tool_input.get('file_path', tool_input.get('path', ''))}*"
    if tool_name in ("Bash", "PowerShell"):
        return f"*{tool_input.get('command', '')}*"
    return "*"


# ── Arrow-key Select ─────────────────────────────────────────────────────────
def _arrow_select(options: list[tuple[str, str]], title: str = "") -> int | None:
    """
    Interactive arrow-key selection using prompt_toolkit.

    Args:
        options: list of (label, description) tuples
        title: optional header text

    Returns:
        index of selected option, or None if cancelled (Ctrl+C / Escape)
    """
    selected = [0]
    result = [None]

    POINTER = _safe("❯", ">")
    SPACE   = "  "

    def get_text():
        lines = []
        if title:
            lines.append(HTML(f"<b>{title}</b>\n"))
        for i, (label, desc) in enumerate(options):
            if i == selected[0]:
                # Focused row: bright pointer + bold label
                pointer_html = f'<style fg="ansibrightcyan"><b>{POINTER}</b></style>'
                label_html   = f'<style fg="ansibrightwhite"><b>{label}</b></style>'
                desc_html    = (
                    f'  <style fg="ansicyan">{desc}</style>' if desc else ""
                )
                lines.append(HTML(f"{pointer_html} {label_html}{desc_html}\n"))
            else:
                # Unfocused row: dim pointer placeholder + normal label
                pointer_html = f'<style fg="ansiblack">{SPACE}</style>'
                label_html   = f'<style fg="ansiwhite">{label}</style>'
                desc_html    = (
                    f'  <style fg="ansidarkgray">{desc}</style>' if desc else ""
                )
                lines.append(HTML(f"{pointer_html} {label_html}{desc_html}\n"))
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

    # Number shortcuts: 1-9
    for _n in range(1, min(10, len(options) + 1)):
        def _make_num_handler(n):
            @kb.add(str(n))
            def _num(event):
                idx = n - 1
                if idx < len(options):
                    result[0] = idx
                    event.app.exit()
        _make_num_handler(_n)

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


# ── Permission Prompt ────────────────────────────────────────────────────────
def prompt_permission(
    tool_name: str, tool_input: dict[str, Any], permission_context: PermissionContext
) -> PermissionDecision:
    desc = format_tool_description(tool_name, tool_input)
    icon = TOOL_ICONS.get(tool_name, _safe("⚡", "[!]"))

    # Show args compactly
    args_str = json.dumps(tool_input, indent=None, ensure_ascii=False)
    if len(args_str) > 120:
        args_str = args_str[:117] + "..."

    # ── Header panel ──
    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1))
    table.add_column(width=3, justify="center")
    table.add_column()
    table.add_row(
        f"[bold {ACCENT_YELLOW}]{icon}[/bold {ACCENT_YELLOW}]",
        f"[bold {TEXT_PRIMARY}]{desc}[/bold {TEXT_PRIMARY}]",
    )
    table.add_row("", f"[{TEXT_DIM}]{args_str}[/{TEXT_DIM}]")
    table.add_row("", f"[{TEXT_DIM}]↑↓ navigate  Enter select  Esc cancel[/{TEXT_DIM}]")

    panel = Panel(
        table,
        title=f"[bold {CLAUDE_ORANGE}]Permission Required[/{CLAUDE_ORANGE}]",
        border_style=ACCENT_YELLOW,
        box=box.HEAVY,
        expand=False,
        padding=(0, 1),
    )
    console.print(panel)

    # ── Arrow-key menu ──
    choices = [
        ("Allow once",      "permit this single call"),
        ("Yes, always",     "add to always-allow list"),
        ("No, deny",        "reject this single call"),
        ("Disable always",  "add to always-deny list"),
    ]

    try:
        idx = _arrow_select(choices, title="")
    except (KeyboardInterrupt, EOFError):
        idx = None

    if idx is None:
        console.print(f"  [{ACCENT_YELLOW}]{WARN}[/{ACCENT_YELLOW}] Cancelled")
        return PermissionDecision("deny", "Cancelled")

    if idx == 0:
        console.print(f"  [{ACCENT_GREEN}]{CHECK}[/{ACCENT_GREEN}] Allowed once")
        return PermissionDecision("allow", "Allowed once")
    elif idx == 1:
        rule_content = get_permission_rule_content(tool_name, tool_input)
        permission_context.always_allow.append(PermissionRuleValue(tool_name, rule_content))
        console.print(f"  [{ACCENT_GREEN}]{CHECK}[/{ACCENT_GREEN}] Always allowed")
        return PermissionDecision("allow", "Always allowed")
    elif idx == 2:
        console.print(f"  [{ACCENT_RED}]{CROSS}[/{ACCENT_RED}] Denied once")
        return PermissionDecision("deny", "Denied once")
    else:
        rule_content = get_permission_rule_content(tool_name, tool_input)
        permission_context.always_deny.append(PermissionRuleValue(tool_name, rule_content))
        console.print(f"  [{ACCENT_RED}]{CROSS}[/{ACCENT_RED}] Always denied")
        return PermissionDecision("deny", "Always denied")


# ── Thinking Spinner ──────────────────────────────────────────────────────────
class ThinkingSpinner:
    def __init__(self, message: str = "Thinking"):
        self.message = message
        self.running = False
        self.thread = None

    def start(self) -> None:
        import threading
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def _animate(self) -> None:
        import time
        idx = 0
        while self.running:
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            # We can use ANSI escape for a clean orange spinner + dim message
            sys.stdout.write(f"\r  \033[38;5;203m{frame}\033[0m \033[2m{self.message}…\033[0m")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        # Clear the line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


# ── Tool Execution Spinner ───────────────────────────────────────────────────
@contextmanager
def tool_spinner(tool_name: str, tool_input: dict[str, Any]):
    import threading
    desc = format_tool_description(tool_name, tool_input)
    icon = TOOL_ICONS.get(tool_name, _safe("⚡", "[!]"))
    start_time = time.perf_counter()

    # Truncate desc for spinner line to avoid wrapping
    max_desc = 60
    short_desc = desc if len(desc) <= max_desc else desc[:max_desc - 1] + "…"

    state = {"success": True, "error": None, "frame": 0, "running": True}

    def spin():
        while state["running"]:
            frame_char = SPINNER_FRAMES[state["frame"]]
            sys.stdout.write(f"\r  \033[2m{frame_char}\033[0m \033[38;5;250m{icon} {short_desc}\033[0m")
            sys.stdout.flush()
            state["frame"] = (state["frame"] + 1) % len(SPINNER_FRAMES)
            time.sleep(0.08)

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()

    try:
        yield state
    finally:
        state["running"] = False
        thread.join(timeout=0.2)
        duration = time.perf_counter() - start_time

        # Clear spinner line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

        if state["success"]:
            dur_str = f"{duration:.1f}s" if duration >= 1 else f"{duration * 1000:.0f}ms"
            console.print(
                f"  [{ACCENT_GREEN}]{CHECK}[/{ACCENT_GREEN}] "
                f"[{TEXT_SECONDARY}]{icon} {desc}[/{TEXT_SECONDARY}]"
                f"  [{TEXT_DIM}]{dur_str}[/{TEXT_DIM}]"
            )
        else:
            console.print(
                f"  [{ACCENT_RED}]{CROSS}[/{ACCENT_RED}] "
                f"[{TEXT_SECONDARY}]{icon} {desc}[/{TEXT_SECONDARY}]"
                f"  [{ACCENT_RED}]{state['error']}[/{ACCENT_RED}]"
                f"  [{TEXT_DIM}]{duration:.1f}s[/{TEXT_DIM}]"
            )


# ── Simple Status Messages ───────────────────────────────────────────────────
def print_success(msg: str) -> None:
    console.print(f"  [{ACCENT_GREEN}]{CHECK}[/{ACCENT_GREEN}] {msg}")


def print_error(msg: str) -> None:
    console.print(f"  [{ACCENT_RED}]{CROSS}[/{ACCENT_RED}] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"  [{ACCENT_YELLOW}]{WARN}[/{ACCENT_YELLOW}] {msg}")


def print_info(msg: str) -> None:
    console.print(f"  [{CLAUDE_ORANGE}]{ARROW_R}[/{CLAUDE_ORANGE}] {msg}")
