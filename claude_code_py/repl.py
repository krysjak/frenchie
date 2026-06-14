from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from claude_code_py.config import RuntimeConfig
from claude_code_py.messages import Message, create_user_message
from claude_code_py.prompts import load_prompt_bundle
from claude_code_py.services.claude_client import ClaudeClient, ClaudeClientError
from claude_code_py.services.cost_tracker import cost_tracker
from claude_code_py.tools import tool_registry
from claude_code_py.services.session_store import SessionStore
from claude_code_py.query import run_turn_loop
from claude_code_py.logger import get_logger


log = get_logger("repl")

# ── Color Palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    BG_SURFACE, BG_ELEVATED,
)


def _safe(s: str, fallback: str) -> str:
    try:
        enc = sys.stdout.encoding or "utf-8"
        s.encode(enc)
        return s
    except Exception:
        return fallback


# ── Unicode helpers ──────────────────────────────────────────────────────────
DOT      = _safe("●", "*")
ARROW_R  = _safe("▸", ">")
ARROW_D  = _safe("▾", "v")
CHECK    = _safe("✔", "[ok]")
CROSS    = _safe("✘", "[x]")
WARN     = _safe("⚠", "[!]")
BLOCK    = _safe("█", "#")
LIGHT    = _safe("░", ".")
LINE_H   = _safe("─", "-")
LINE_V   = _safe("│", "|")
CORNER_TL= _safe("╭", "+")
CORNER_TR= _safe("╮", "+")
CORNER_BL= _safe("╰", "+")
CORNER_BR= _safe("╯", "+")
DIAMOND  = _safe("◆", "*")
CIRCLE   = _safe("○", "o")
BULLET   = _safe("·", "-")
ARROW_DOWN = _safe("⬇", "v")


# ── Claude Logo ──────────────────────────────────────────────────────────────
def _build_logo() -> list[str]:
    """French bulldog mascot (Braille art)."""
    o = CLAUDE_ORANGE
    return [
        f" [{o}]⠄⠄⠄⠄⠄⠄⣠⢿⡄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⡿⣄[/]",
        f" [{o}]⠄⠄⠄⠄⠄⣰⢳⡌⣿⢀⣀⣀⣀⠄⠄⠄⠄⢀⣀⣀⡀⡞⢠⣎⣆[/]",
        f" [{o}]⠄⠄⠄⠄⢸⣣⣿⣧⠛⠉⠉⠄⠈⠉⠉⠉⠉⠉⠁⠈⠉⠁⢴⣧⣌⡆[/]",
        f" [{o}]⠄⠄⠄⠄⣾⣻⠛⠁⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⢛⣿⣷[/]",
        f" [{o}]⠄⠄⠄⠄⣿⡏⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢰⣿⣿[/]",
        f" [{o}]⠄⠄⠄⠄⣿⣷⡤⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢹⣾⣿⣿[/]",
        f" [{o}]⠄⠄⠄⠄⡿⣏⣧⣤⣀⣀⠄⠄⠄⣺⠄⢠⡏⠄⠄⠄⣀⣤⣤⣽⣿⣿[/]",
        f" [{o}]⠄⠄⠄⢰⢷⣿⢿⣷⣉⠛⣻⣦⣀⡿⠄⠈⠃⠰⣶⣞⠋⣉⣿⠗⠉⣿⡇[/]",
        f" [{o}]⠄⠄⠄⣾⣸⣯⡴⠈⠙⠛⠛⠋⠁⠄⠬⠭⣗⡀⠹⠿⣿⣫⡅⠄⣠⣿⣿[/]",
        f"[{o}]⠠⣤⡶⢿⣗⣿⣿⣦⠄⠄⠄⠄⠄⠐⠒⠒⠚⢯⡀⠸⣿⣿⣧⣾⣿⣿⣿⣦⣤⠄[/]",
        f" [{o}]⠄⠄⠉⠻⣿⣿⣿⣿⣿⣓⢀⣴⣿⣿⣿⣿⣤⣶⡆⣰⣿⣿⣿⣿⣿⣿⠟⠉[/]",
        f" [{o}]⠄⠄⠄⢀⣿⠙⣿⣿⣿⡛⡿⠛⠛⢻⣿⡿⠛⠛⠋⠘⣻⣿⣿⣿⠋⣿⡀[/]",
        f"[{o}]⣀⣴⣞⣉⣀⣢⢹⣿⣿⣷⡅⠄⢀⣨⣿⣇⣀⡀⠄⣸⣿⣿⣿⡇⣰⣟⣉⣓⣤⣀[/]",
        f" [{o}]⠉⠉⠉⠉⠉⠻⣦⡻⣿⣿⣿⣦⣿⣿⣿⡿⢿⣿⣾⣿⣿⣿⣿⣷⠏⠉⠉⠉⠉[/]",
        f" [{o}]⠄⠄⠄⠄⠄⣰⠋⣹⣦⣝⡻⠿⣿⣿⡿⠿⠿⠿⢻⣿⣿⣿⡿⠻⣆[/]",
        f" [{o}]⠄⠄⠄⠄⣼⡷⠟⠛⠙⠻⣿⠷⣶⣶⣶⣶⣶⣶⣿⣿⠟⠋⠛⠲⢮⣧[/]",
        f" [{o}]⠄⠄⠄⠄⠁⠄⠄⠄⠄⠄⢸⢀⡴⠋⠉⠉⠹⢇⢀⡇⠄⠄⠄⠄⠄⠄⠁[/]",
        f" [{o}]⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢸⡟⠁⠄⠄⠄⠄⠈⢻⡇[/]",
    ]


# ── Window Title ────────────────────────────────────────────────────────────

def _clear_and_set_title():
    """Clear the entire terminal and set the window title to Frenchie."""
    sys.stdout.write("\033[2J\033[H")        # clear screen + cursor home
    sys.stdout.write("\033]0;Frenchie\007")   # OSC: set window title
    sys.stdout.flush()


def _build_simple_logo() -> list[str]:
    """Compact bulldog for narrow terminals."""
    o = CLAUDE_ORANGE
    d = CLAUDE_DIM
    return [
        f"  [{d}]╭─╮        ╭─╮[/]",
        f"  [{o}]│ ╰╮      ╭╯ │[/]",
        f"  [{o}]│  ╰──────╯  │[/]",
        f"  [{o}]│  ●      ●  │[/]",
        f"  [{o}]│    ╭──╮    │[/]",
        f"  [{o}]╰────╯  ╰────╯[/]",
    ]


# ── Welcome Banner ──────────────────────────────────────────────────────────
def _render_welcome(console: Console, config: RuntimeConfig) -> None:
    """Welcome panel with companion sprite."""
    from claude_code_py import __version__
    from claude_code_py.components.companion import get_companion
    version_display = f"v{__version__}"

    safe_mode = (
        os.environ.get("FRENCH_SAFE_MODE") or os.environ.get("CLAUDE_CODE_SAFE_MODE")
    ) == "1"

    # ── Shorten path ──
    cwd_str = str(config.cwd)
    if len(cwd_str) > 40:
        parts = cwd_str.replace("\\", "/").split("/")
        if len(parts) > 2:
            cwd_str = ".../" + "/".join(parts[-2:])
        else:
            cwd_str = "..." + cwd_str[-37:]

    # ── Provider label ──
    if config.api_provider != "anthropic":
        url_text = f" [{TEXT_DIM}]({config.api_base_url})[/]" if config.api_base_url else ""
        provider_label = f"{config.api_provider}{url_text}"
    else:
        provider_label = config.api_provider

    # ── Render companion + info side by side ──
    companion = get_companion()
    buddy = companion.render()

    label_w = 10
    info_lines = [
        f"[bold {TEXT_PRIMARY}]Frenchie[/]  [{TEXT_DIM}]{version_display}[/]",
        "",
        f"  [{TEXT_SECONDARY}]{'provider':<{label_w}}[/][{CLAUDE_LIGHT}]{provider_label}[/]",
        f"  [{TEXT_SECONDARY}]{'model':<{label_w}}[/][bold {CLAUDE_ORANGE}]{config.model}[/]",
        f"  [{TEXT_SECONDARY}]{'cwd':<{label_w}}[/][{TEXT_DIM}]{cwd_str}[/]",
    ]
    if safe_mode:
        info_lines.append(f"  [{ACCENT_YELLOW}]safe mode active[/]")

    panel = Panel(
        "\n".join(info_lines),
        border_style=CLAUDE_DIM,
        expand=False,
        box=box.SIMPLE,
        padding=(1, 2),
    )
    console.print(buddy)
    console.print(panel)
    console.print(
        f"  [{TEXT_DIM}]/help  /model  /provider  /init  Tab:mode  Ctrl+L:clear  Ctrl+D:exit[/]"
    )


# ── Status Line ──────────────────────────────────────────────────────────────
def _render_status(console: Console, config: RuntimeConfig, mcp_failures: int = 0) -> None:
    parts = []
    if mcp_failures > 0:
        word = "issue" if mcp_failures == 1 else "issues"
        parts.append(f"[{ACCENT_YELLOW}]{WARN} {mcp_failures} MCP {word}[/]")
    if parts:
        console.print(f"  {' '.join(parts)}  [{TEXT_DIM}]{BULLET} /doctor for details[/]")
    console.print()


# ── Prompt ───────────────────────────────────────────────────────────────────
def _build_prompt(cwd_name: str, mode: str = "default") -> str:
    """Build a styled prompt string for prompt_toolkit."""
    import shutil
    columns, _ = shutil.get_terminal_size((80, 24))
    line = "─" * columns

    if mode == "plan":
        prompt_text = f'<style fg="{ACCENT_CYAN}"><b>Task (plan)</b></style> <style fg="{TEXT_DIM}">&gt;</style> '
    elif mode == "auto":
        prompt_text = f'<style fg="{ACCENT_GREEN}"><b>Task (auto)</b></style> <style fg="{TEXT_DIM}">&gt;</style> '
    else:
        # Build mode: keep it simple and clean, just >
        prompt_text = f'<style fg="{CLAUDE_ORANGE}"><b>&gt;</b></style> '

    return (
        f'<style fg="#444444">{line}</style>\n'
        f'{prompt_text}'
    )


def _shorten_path(path: Path | str, max_len: int = 48) -> str:
    path_str = str(path)
    if len(path_str) <= max_len:
        return path_str
    parts = path_str.replace("\\", "/").split("/")
    if len(parts) > 2:
        shortened = ".../" + "/".join(parts[-2:])
        if len(shortened) <= max_len:
            return shortened
    return "..." + path_str[-(max_len - 3):]


def _mode_label(mode: str) -> str:
    return "build" if mode == "default" else mode


def _mode_color(mode: str) -> str:
    if mode == "plan":
        return CLAUDE_LIGHT
    if mode == "auto":
        return ACCENT_GREEN
    return CLAUDE_ORANGE


def _render_welcome(console: Console, config: RuntimeConfig) -> None:
    """Render an opencode-inspired compact welcome screen."""
    from claude_code_py import __version__

    from claude_code_py.services.state_store import StateStore

    safe_mode = (
        os.environ.get("FRENCH_SAFE_MODE") or os.environ.get("CLAUDE_CODE_SAFE_MODE")
    ) == "1"
    mode = StateStore().load().get("permission_mode", "default")
    mode_name = _mode_label(mode)
    mode_style = _mode_color(mode)

    if config.api_provider != "anthropic":
        url_text = f" [{TEXT_DIM}]({config.api_base_url})[/]" if config.api_base_url else ""
        provider_label = f"{config.api_provider}{url_text}"
    else:
        provider_label = "anthropic"

    grid = Table.grid(expand=False)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        f"[bold {CLAUDE_ORANGE}]FRENCHIE[/] [{TEXT_DIM}]v{__version__}[/]",
        f"[bold black on {mode_style}] {mode_name.upper()} [/]",
    )
    grid.add_row(
        f"[{TEXT_SECONDARY}]model[/] [bold {TEXT_PRIMARY}]{config.model}[/]",
        f"[{TEXT_SECONDARY}]provider[/] [{CLAUDE_LIGHT}]{provider_label}[/]",
    )
    grid.add_row(
        f"[{TEXT_SECONDARY}]cwd[/] [{TEXT_DIM}]{_shorten_path(config.cwd)}[/]",
        f"[{TEXT_SECONDARY}]theme[/] [{CLAUDE_ORANGE}]red/black[/]",
    )
    if safe_mode:
        grid.add_row(f"[{ACCENT_YELLOW}]safe mode active[/]", "")

    console.print(
        Panel(
            grid,
            title=f"[bold {CLAUDE_ORANGE}]open terminal[/]",
            title_align="left",
            subtitle=f"[{TEXT_DIM}]/help  /model  /mode  /doctor[/]",
            subtitle_align="left",
            border_style=CLAUDE_ORANGE,
            expand=False,
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _build_prompt(cwd_name: str, mode: str = "default") -> str:
    """Build a compact red/black opencode-like prompt."""
    mode_name = _mode_label(mode)
    mode_color = _mode_color(mode)
    action = "plan" if mode == "plan" else ("auto" if mode == "auto" else "ask")
    return (
        f'<style fg="{CLAUDE_ORANGE}"><b>frenchie</b></style>'
        f'<style fg="{TEXT_DIM}">:</style>'
        f'<style fg="{TEXT_SECONDARY}">{cwd_name}</style> '
        f'<style fg="black" bg="{mode_color}"><b> {mode_name} </b></style> '
        f'<style fg="{TEXT_DIM}">{action}</style> '
        f'<style fg="{CLAUDE_ORANGE}"><b>></b></style> '
    )


# ── Completion Menu Style ────────────────────────────────────────────────────
REPL_STYLE = Style.from_dict({
    # Prompt
    "":                f"fg:{TEXT_PRIMARY}",
    # Completion menu
    "completion-menu.completion":              f"bg:{BG_ELEVATED} {TEXT_PRIMARY}",
    "completion-menu.completion.current":      f"bg:{CLAUDE_ORANGE} {TEXT_PRIMARY} bold",
    "completion-menu.meta.completion":         f"bg:{BG_SURFACE} {TEXT_DIM}",
    "completion-menu.meta.completion.current": f"bg:{CLAUDE_DIM} {TEXT_PRIMARY}",
    # Scrollbar
    "scrollbar.background": f"bg:{BG_SURFACE}",
    "scrollbar.button":     f"bg:{TEXT_DIM}",
    # Auto-suggest
    "auto-suggestion":      f"fg:{TEXT_DIM}",
    # Toolbar & Right Prompt
    "bottom-toolbar":       f"bg:{BG_SURFACE} fg:{TEXT_DIM}",
    "rprompt":              f"fg:{TEXT_DIM}",
})


# ── Completer ────────────────────────────────────────────────────────────────
class ClaudeREPLCompleter(Completer):
    def __init__(self, command_registry, cwd: Path) -> None:
        self.command_registry = command_registry
        self.cwd = cwd

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/") and " " not in text:
            query = text[1:].lower()
            for cmd in sorted(self.command_registry.commands.keys()):
                if cmd.lower().startswith(query):
                    obj = self.command_registry.commands.get(cmd)
                    desc = obj.description if obj else ""
                    yield Completion(
                        f"/{cmd}", start_position=-len(text),
                        display_meta=desc,
                    )
            return

        if text.startswith("/"):
            parts = text.split()
            cmd_name = parts[0][1:]

            subcommands_map = {
                "mcp": ["serve", "list", "servers", "status", "tools", "call", "resources", "enable", "disable"],
                "config": ["show", "list", "path", "set", "reset"],
                "permissions": ["show", "mode", "allow", "deny", "ask", "reset"],
                "memory": ["list", "project", "user", "edit"],
                "model": ["set", "opus", "sonnet", "haiku", "fable"],
                "provider": ["openai", "lm-studio", "anthropic"],
                "effort": ["low", "medium", "high", "xhigh"],
            }

            if cmd_name in subcommands_map:
                subcmds = subcommands_map[cmd_name]
                if len(parts) == 1 and text.endswith(" "):
                    for sub in subcmds:
                        yield Completion(sub, start_position=0, display_meta=f"{cmd_name} subcommand")
                    return
                elif len(parts) == 2 and not text.endswith(" "):
                    sq = parts[1].lower()
                    for sub in subcmds:
                        if sub.lower().startswith(sq):
                            yield Completion(sub, start_position=-len(parts[1]), display_meta=f"{cmd_name} subcommand")
                    return
                elif len(parts) == 2 and parts[1] in {"enable", "disable"} and text.endswith(" "):
                    from claude_code_py.services.mcp.config import load_mcp_config
                    try:
                        for name in sorted(load_mcp_config(Path.home(), self.cwd)):
                            yield Completion(name, start_position=0, display_meta="MCP Server")
                    except Exception:
                        pass
                    return
                elif len(parts) == 3 and parts[1] in {"enable", "disable"} and not text.endswith(" "):
                    from claude_code_py.services.mcp.config import load_mcp_config
                    try:
                        q = parts[2].lower()
                        for name in sorted(load_mcp_config(Path.home(), self.cwd)):
                            if name.lower().startswith(q):
                                yield Completion(name, start_position=-len(parts[2]), display_meta="MCP Server")
                    except Exception:
                        pass
                    return

            last_word = text.split()[-1] if text.strip() else ""
        else:
            last_word = text.split()[-1] if text.strip() else ""

        if last_word and not last_word.startswith("/"):
            try:
                pp = Path(last_word)
                if last_word.endswith(("/", "\\")) or (self.cwd / pp).is_dir():
                    sd, sp = self.cwd / pp, "*"
                else:
                    sd, sp = self.cwd / pp.parent, pp.name + "*"
                if sd.exists() and sd.is_dir():
                    for entry in sd.glob(sp):
                        try:
                            rel = entry.relative_to(self.cwd)
                            name = str(rel).replace("\\", "/")
                            meta = "dir" if entry.is_dir() else "file"
                            if entry.is_dir():
                                name += "/"
                            if name.lower().startswith(str(pp).replace("\\", "/").lower()):
                                yield Completion(name, start_position=-len(last_word), display_meta=meta)
                        except ValueError:
                            pass
            except Exception:
                pass


# ── Per-turn Summary ─────────────────────────────────────────────────────────
def _print_turn_summary(console: Console, cost_delta: float, tokens_delta: int, duration_delta: float) -> None:
    if cost_delta <= 0 and tokens_delta <= 0:
        return

    parts = []
    if tokens_delta > 0:
        parts.append(f"[{ACCENT_CYAN}]+{tokens_delta:,} tokens[/{ACCENT_CYAN}]")
    if cost_delta > 0:
        parts.append(f"[{ACCENT_GREEN}]+${cost_delta:.4f}[/{ACCENT_GREEN}]")
    if duration_delta > 0:
        parts.append(f"[{ACCENT_YELLOW}]{duration_delta:.1f}s[/{ACCENT_YELLOW}]")

    summary = f"  {BULLET} " + f"  {LINE_V}  ".join(parts)
    console.print(f"[{TEXT_DIM}]{summary}[/{TEXT_DIM}]")


# ── Main REPL ────────────────────────────────────────────────────────────────
def run_repl(config: RuntimeConfig) -> None:
    log.info("Starting REPL session — model=%s, cwd=%s", config.model, config.cwd)
    console = Console()

    global _repl_config
    _repl_config = config

    # ── Clear terminal & set title ──
    _clear_and_set_title()

    # Load state
    cost_tracker.load_from_state(config.home)
    from claude_code_py.services.mcp.client import initialize_mcp_servers, mcp_manager
    initialize_mcp_servers(config.home, config.cwd)
    log.debug("MCP servers: %d connected, %d failed", len(mcp_manager.clients), len(mcp_manager.failures))

    # ── Banner ──
    _render_welcome(console, config)
    _render_status(console, config, mcp_failures=len(mcp_manager.failures))

    # ── Client init ──
    store = SessionStore(config.home, config.cwd)
    client = ClaudeClient(config.model)
    try:
        client.validate()
        log.debug("ClaudeClient validated successfully")
    except ClaudeClientError as exc:
        log.warning("Client validation failed: %s", exc)
        console.print(Panel(
            f"[bold red]{exc}[/]\n\n"
            f"Pick a provider with [bold]/provider[/] (LM Studio needs no key), "
            f"or run [bold]/login[/] to save an Anthropic API key.",
            title=f"[{CLAUDE_ORANGE}]Connection Error[/]",
            border_style="red", box=box.HEAVY,
        ))
        return

    messages: list[Message] = store.load()
    system_prompt = load_prompt_bundle().render_system_prompt(config.model)

    from claude_code_py.commands import command_registry
    from claude_code_py.components.companion import get_companion
    from claude_code_py.components.status_bar import get_status_bar

    # ── Prompt session ──
    from claude_code_py.services.config_store import config_dir
    history_file = config_dir(config.home) / "repl_history.txt"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # ── Key bindings ──
    kb = KeyBindings()

    @kb.add("c-l")
    def _clear_screen(event):
        """Ctrl+L: clear terminal screen."""
        _clear_and_set_title()
        _render_welcome(console, config)
        _render_status(console, config, mcp_failures=len(mcp_manager.failures))

    @kb.add("c-d")
    def _exit_repl(event):
        """Ctrl+D: exit."""
        # Just exit the app — the outer loop catches EOFError and prints "Goodbye"
        event.app.exit()

    from prompt_toolkit.filters import Condition

    @Condition
    def is_buffer_empty():
        from prompt_toolkit.application import get_app
        app = get_app()
        return not app.current_buffer.text.strip()

    @kb.add("tab", filter=is_buffer_empty)
    def _toggle_mode(event):
        """Tab: toggle mode when prompt is empty."""
        from claude_code_py.services.state_store import StateStore
        store = StateStore()
        current = store.load().get("permission_mode", "default")
        if current == "default":
            new_mode = "plan"
        elif current == "plan":
            new_mode = "auto"
        else:
            new_mode = "default"

        store.set("permission_mode", new_mode)

        # Update status bar live
        status_bar.update(mode=new_mode)

        pass

        # Invalidate app to redraw prompt prefix and status bar
        event.app.invalidate()

    session = PromptSession(
        completer=ClaudeREPLCompleter(command_registry, config.cwd),
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        style=REPL_STYLE,
        key_bindings=kb,
    )

    from claude_code_py.permissions import PermissionContext
    permission_context = PermissionContext()

    cwd_name = config.cwd.name or str(config.cwd)
    if len(cwd_name) > 25:
        cwd_name = cwd_name[:22] + "..."

    # ── Init companion + status bar ──
    status_bar = get_status_bar()

    def get_bottom_toolbar():
        from claude_code_py.services.state_store import StateStore
        from claude_code_py.components.status_bar import get_status_bar
        mode = StateStore().load().get("permission_mode", "default").upper()
        if mode == "DEFAULT":
            mode = "BUILD"
        
        sb = get_status_bar()
        prov = sb.provider or "unknown"
        cost_str = f"${sb.cost:.4f}" if sb.cost > 0 else "$0.00"
        
        mode_color = CLAUDE_LIGHT if mode == "PLAN" else (ACCENT_GREEN if mode == "AUTO" else CLAUDE_ORANGE)
        
        parts = [
            f'🧠 <b>{sb.model}</b>',
            f'☁️ <style fg="{ACCENT_CYAN}">{prov}</style>',
            f'🔧 <style fg="{ACCENT_GREEN}">{sb.tool_count} tools</style>',
            f'⚡ <style fg="{ACCENT_CYAN}">{sb.effort.upper()}</style>',
            f'💰 <style fg="{ACCENT_YELLOW}">{cost_str}</style>',
            f'<style fg="black" bg="{mode_color}"><b> {mode} </b></style>',
            f'<style fg="{TEXT_DIM}">Tab:toggle · Ctrl+L:clear · Ctrl+D:exit</style>'
        ]
        return HTML("  ·  ".join(parts))

    from claude_code_py.services.state_store import StateStore

    def get_bottom_toolbar():
        from claude_code_py.components.status_bar import get_status_bar

        raw_mode = StateStore().load().get("permission_mode", "default")
        mode = _mode_label(raw_mode).upper()
        sb = get_status_bar()
        prov = sb.provider or "unknown"
        cost_str = f"${sb.cost:.4f}" if sb.cost > 0 else "$0.00"
        mode_color = _mode_color(raw_mode)
        parts = [
            f'<style fg="{CLAUDE_ORANGE}"><b>model</b></style> <b>{sb.model}</b>',
            f'<style fg="{CLAUDE_ORANGE}"><b>provider</b></style> <style fg="{TEXT_SECONDARY}">{prov}</style>',
            f'<style fg="{CLAUDE_ORANGE}"><b>tools</b></style> <style fg="{ACCENT_GREEN}">{sb.tool_count}</style>',
            f'<style fg="{CLAUDE_ORANGE}"><b>effort</b></style> <style fg="{TEXT_SECONDARY}">{sb.effort.upper()}</style>',
            f'<style fg="{CLAUDE_ORANGE}"><b>cost</b></style> <style fg="{ACCENT_YELLOW}">{cost_str}</style>',
            f'<style fg="black" bg="{mode_color}"><b> {mode} </b></style>',
            f'<style fg="{TEXT_DIM}">Tab mode | Ctrl+L clear | Ctrl+D exit</style>',
        ]
        return HTML("  |  ".join(parts))

    current_mode = StateStore().load().get("permission_mode", "default")

    status_bar.update(
        model=config.model,
        provider=config.api_provider,
        tool_count=len(tool_registry.names()),
        mcp_connected=len(mcp_manager.clients),
        mcp_failed=len(mcp_manager.failures),
        safe_mode=(os.environ.get("FRENCH_SAFE_MODE") or os.environ.get("CLAUDE_CODE_SAFE_MODE")) == "1",
        effort=os.environ.get("FRENCH_EFFORT") or os.environ.get("CLAUDE_EFFORT") or "high",
        mode=current_mode,
    )

    while True:
        current_mode = StateStore().load().get("permission_mode", "default")
        status_bar.update(
            mode=current_mode,
            tool_count=len(tool_registry.names()),
            mcp_connected=len(mcp_manager.clients),
            mcp_failed=len(mcp_manager.failures),
        )

        def get_prompt():
            mode = StateStore().load().get("permission_mode", "default")
            return HTML(_build_prompt(cwd_name, mode))

        def get_rprompt():
            from claude_code_py.services.auth import check_auth_status
            from claude_code_py.services.cost_tracker import cost_tracker
            auth = check_auth_status(config.home)
            from claude_code_py.services.state_store import StateStore
            mode = StateStore().load().get("permission_mode", "default").upper()
            if mode == "DEFAULT":
                mode = "BUILD"
            
            mode_color = ACCENT_CYAN if mode == "PLAN" else (ACCENT_GREEN if mode == "AUTO" else CLAUDE_ORANGE)
            mode_html = f'<style fg="{mode_color}"><b>[{mode}]</b></style>'

            if auth["status"] != "authenticated":
                return HTML(f'{mode_html} · <style fg="{ACCENT_RED}">Not logged in</style>')
            cost_str = f"${cost_tracker.total_cost_usd:.4f}" if cost_tracker.total_cost_usd > 0 else "$0.00"
            return HTML(f'{mode_html} · <style fg="{TEXT_DIM}">{config.model} · {cost_str}</style>')

        def get_rprompt():
            from claude_code_py.services.auth import check_auth_status
            from claude_code_py.services.cost_tracker import cost_tracker

            auth = check_auth_status(config.home)
            raw_mode = StateStore().load().get("permission_mode", "default")
            mode = _mode_label(raw_mode).upper()
            mode_html = f'<style fg="{_mode_color(raw_mode)}"><b>[{mode}]</b></style>'
            if auth["status"] != "authenticated":
                return HTML(f'{mode_html} | <style fg="{ACCENT_RED}">not logged in</style>')
            cost_str = f"${cost_tracker.total_cost_usd:.4f}" if cost_tracker.total_cost_usd > 0 else "$0.00"
            return HTML(f'{mode_html} | <style fg="{TEXT_DIM}">{config.model} | {cost_str}</style>')

        try:
            # Mark prompt start for VS Code Shell Integration
            sys.stdout.write("\033]133;A\007")
            sys.stdout.flush()

            user_input = session.prompt(
                get_prompt,
                rprompt=get_rprompt,
                bottom_toolbar=get_bottom_toolbar,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\033]133;D;0\007")
            sys.stdout.flush()
            console.print(f"\n  [{CLAUDE_ORANGE}]{ARROW_R}[/] [{TEXT_DIM}]Goodbye[/{TEXT_DIM}]")
            break

        if not user_input:
            sys.stdout.write("\033[F\033[K\033[F\033[K")
            sys.stdout.flush()
            continue

        # Clean prompt horizontal line and prefix symbol from history
        sys.stdout.write("\033[F\033[K\033[F\033[K")
        sys.stdout.flush()

        # Mark command start and output start for VS Code Shell Integration
        sys.stdout.write("\033]133;B\007\033]133;C\007")
        sys.stdout.flush()

        # Display query using the official brand format in history
        console.print(
            f"[bold {CLAUDE_ORANGE}]frenchie[/][{TEXT_DIM}]:[/]"
            f"[{TEXT_SECONDARY}]{cwd_name}[/] "
            f"[bold {CLAUDE_ORANGE}]>[/] {user_input}"
        )

        # ── Slash commands ──
        if user_input.startswith("/"):
            parts = user_input[1:].split()
            if not parts:
                sys.stdout.write("\033]133;D;0\007")
                sys.stdout.flush()
                continue
            cmd_name, cmd_args = parts[0], parts[1:]
            # Snapshot settings so commands like /provider and /model take effect live.
            before = (config.model, config.api_provider, config.api_base_url)
            try:
                command_registry.run(cmd_name, config, cmd_args)
                sys.stdout.write("\033]133;D;0\007")
            except Exception as e:
                log.error("Command '%s' failed: %s", cmd_name, e)
                from rich.markup import escape as _esc
                console.print(f"  [{CLAUDE_ORANGE}]{CROSS}[/] [bold red]{cmd_name}:[/] {_esc(str(e))}")
                sys.stdout.write("\033]133;D;1\007")
            sys.stdout.flush()
            # If the command changed model/provider, rebuild config + client now.
            new_config = RuntimeConfig.from_environment()
            if (new_config.model, new_config.api_provider, new_config.api_base_url) != before:
                log.info("Config changed — model=%s, provider=%s", new_config.model, new_config.api_provider)
                config = new_config
                _repl_config = config
                client = ClaudeClient(config.model)
                system_prompt = load_prompt_bundle().render_system_prompt(config.model)
                status_bar.update(model=config.model, provider=config.api_provider)
                _clear_and_set_title()
                _render_welcome(console, config)
                _render_status(console, config, mcp_failures=len(mcp_manager.failures))
            continue

        # ── Chat turn ──
        user_msg = create_user_message(user_input)
        store.append(user_msg)
        messages.append(user_msg)

        cost_before = cost_tracker.total_cost_usd
        tokens_before = cost_tracker.total_input_tokens + cost_tracker.total_output_tokens
        duration_before = cost_tracker.total_api_duration

        # Rebuild system prompt to capture the active mode changes
        system_prompt = load_prompt_bundle().render_system_prompt(config.model)

        try:
            run_turn_loop(
                client=client,
                store=store,
                messages=messages,
                system_prompt=system_prompt,
                stream=True,
                max_turns=15,
                permission_context=permission_context,
            )
            sys.stdout.write("\033]133;D;0\007")
        except KeyboardInterrupt:
            log.info("User interrupted via Ctrl+C")
            console.print(f"\n  [{ACCENT_YELLOW}]{ARROW_R}[/{ACCENT_YELLOW}] Interrupted")
            sys.stdout.write("\033]133;D;130\007")
        except Exception as e:
            log.exception("Chat turn error: %s", e)
            from rich.markup import escape as _esc
            console.print(f"\n  [{CLAUDE_ORANGE}]{CROSS}[/] [bold red]Error:[/] {_esc(str(e))}")
            sys.stdout.write("\033]133;D;1\007")
        finally:
            sys.stdout.flush()
            cost_tracker.save_to_state(config.home)
            # ── Live StatusBar update after each turn ──
            status_bar.update(
                cost=cost_tracker.total_cost_usd,
                tool_count=len(tool_registry.names()),
                mcp_connected=len(mcp_manager.clients),
                mcp_failed=len(mcp_manager.failures),
            )
            _print_turn_summary(
                console,
                cost_tracker.total_cost_usd - cost_before,
                (cost_tracker.total_input_tokens + cost_tracker.total_output_tokens) - tokens_before,
                cost_tracker.total_api_duration - duration_before,
            )
