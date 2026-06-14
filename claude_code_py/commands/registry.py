from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
import json

from claude_code_py.config import RuntimeConfig
from claude_code_py.commands.model import Command
from claude_code_py.services.config_store import config_path, load_config, save_config, set_config_value
from claude_code_py.services.memory_store import ensure_memory_file, list_memory_files, open_in_editor
from claude_code_py.services.read_state import ReadStateStore
from claude_code_py.query import run_single_turn
from claude_code_py.mcp.explorer import ClaudeCodeExplorer
from claude_code_py.mcp.stdio import serve_stdio
from claude_code_py.tools import tool_registry
import sys
import select


CommandHandler = Callable[..., None]


@dataclass
class CommandRegistry:
    handlers: dict[str, CommandHandler] = field(default_factory=dict)
    commands: dict[str, Command] = field(default_factory=dict)

    def register(self, name: str, handler: CommandHandler, description: str = "", aliases: tuple[str, ...] = ()) -> None:
        self.handlers[name] = handler
        command = Command(name=name, description=description, handler=handler, aliases=aliases)
        self.commands[name] = command
        for alias in aliases:
            self.commands[alias] = command

    def run(self, name: str, config: RuntimeConfig, *args: Any) -> None:
        handler = self.handlers.get(name)
        if handler is None and name in self.commands:
            handler = self.commands[name].handler
        if handler is None:
            raise click.ClickException(f"Command is not ported yet: {name}")
        handler(config, *args)

    def run_default(self, config: RuntimeConfig) -> None:
        from claude_code_py.repl import run_repl
        run_repl(config)

    def get_names(self) -> list[str]:
        """Return sorted list of registered command names (excluding aliases)."""
        names = set()
        for cmd in self.commands.values():
            if cmd.name not in names:
                names.add(cmd.name)
        return sorted(names)


command_registry = CommandRegistry()


def _doctor(config: RuntimeConfig) -> None:
    click.echo("Doctor")
    click.echo(f"cwd: {config.cwd}")
    click.echo(f"home: {config.home}")
    from claude_code_py.services.auth import check_auth_status
    auth = check_auth_status(config.home)
    if auth["status"] == "authenticated":
        click.echo(f"auth: Authenticated ({auth['source']})")
    else:
        click.echo("auth: Not authenticated")
    click.echo(f"model: {config.model}")
    click.echo(f"remote: {config.is_remote}")

    from claude_code_py.services.mcp.client import mcp_manager
    if mcp_manager.failures:
        click.echo("\nMCP Server Issues:")
        for name, failure in mcp_manager.failures.items():
            click.echo(f"  ⚠️ {name}: {failure}")


def _help(config: RuntimeConfig) -> None:
    del config
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()

    # Group commands by category
    categories = {
        "General": ["help", "version", "status", "doctor", "exit"],
        "Chat": ["run", "resume", "clear", "compact"],
        "Model": ["model", "provider", "advisor", "effort"],
        "Analysis": ["usage", "cost", "diff", "code-review", "agents"],
        "Setup": ["init", "login", "logout", "mode", "memory", "config", "permissions", "update"],
        "Tools": ["tools", "tool", "mcp", "files", "plugins", "skills", "sandbox", "voice"],
        "System": ["logs"],
        "IDE": ["bridge", "web"],
    }

    table = Table(box=None, show_header=True, header_style="bold #e5484d", padding=(0, 2), show_edge=False)
    table.add_column("Command", style="bold #e5484d", width=16)
    table.add_column("Description", style="#b0b0b0")
    table.add_column("Aliases", style="#6c6c6c", width=16)

    seen: set[str] = set()
    for cat_name, cat_cmds in categories.items():
        table.add_row(f"[bold white]{cat_name}[/bold white]", "", "")
        for cmd_name in cat_cmds:
            cmd = command_registry.commands.get(cmd_name)
            if cmd and cmd.name not in seen:
                seen.add(cmd.name)
                aliases = ", ".join(cmd.aliases) if cmd.aliases else ""
                table.add_row(f"  /{cmd.name}", cmd.description, aliases)
        table.add_row("", "", "")

    panel = Panel(table, title="[bold #e5484d]Commands[/bold #e5484d]", border_style="#e5484d", box=box.ROUNDED, expand=False)
    console.print(panel)
    console.print(f"  [#6c6c6c]Tip: Use [bold #e5484d]/<command>[/bold #e5484d] in chat, or [bold]frenchie <command>[/bold] from shell[/#6c6c6c]")


def _status(config: RuntimeConfig) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    import os
    console = Console()

    table = Table(box=None, show_header=False, padding=(0, 2), show_edge=False)
    table.add_column(width=20, style="#6c6c6c")
    table.add_column()

    table.add_row("Version", f"[bold #e5484d]{__import__('claude_code_py').__version__}[/bold #e5484d]")
    table.add_row("Working directory", f"[#b0b0b0]{config.cwd}[/#b0b0b0]")
    table.add_row("Config", f"[#b0b0b0]{config_path(config.home)}[/#b0b0b0]")

    from claude_code_py.services.auth import check_auth_status
    auth = check_auth_status(config.home)
    if auth["status"] == "authenticated":
        table.add_row("Authentication", f"[#5fd787]Authenticated[/#5fd787] ([#6c6c6c]{auth['source']}[/#6c6c6c])")
    else:
        table.add_row("Authentication", "[#ff5f5f]Not authenticated[/#ff5f5f]")

    table.add_row("Model", f"[bold #e5484d]{config.model}[/bold #e5484d]")
    table.add_row("Tools", f"[#ff8787]{len(tool_registry.names())}[/#ff8787] registered")
    table.add_row("Remote", f"[#b0b0b0]{config.is_remote}[/#b0b0b0]")
    table.add_row("Safe mode", "[#ffd75f]ON[/#ffd75f]" if (os.environ.get("FRENCH_SAFE_MODE") or os.environ.get("CLAUDE_CODE_SAFE_MODE")) == "1" else "[#b0b0b0]OFF[/#b0b0b0]")
    table.add_row("Effort", f"[#ff8787]{os.environ.get('FRENCH_EFFORT') or os.environ.get('CLAUDE_EFFORT') or 'high'}[/#ff8787]")

    from claude_code_py.services.mcp.client import mcp_manager
    table.add_row("MCP servers", f"[#ff8787]{len(mcp_manager.clients)}[/#ff8787] connected")

    panel = Panel(table, title="[bold #e5484d]Status[/bold #e5484d]", border_style="#e5484d", box=box.ROUNDED, expand=False)
    console.print(panel)


def _config(config: RuntimeConfig, args: list[str] | None = None) -> None:
    args = args or []
    if not args or args[0] in {"list", "show"}:
        click.echo(json.dumps(load_config(config.home), indent=2, ensure_ascii=False))
        return
    if args[0] == "path":
        click.echo(str(config_path(config.home)))
        return
    if args[0] == "set":
        if len(args) < 3:
            raise click.ClickException("usage: config set <key> <json-value>")
        try:
            value = json.loads(args[2])
        except json.JSONDecodeError:
            value = args[2]
        path = set_config_value(args[1], value, config.home)
        click.echo(f"Saved {path}")
        return
    if args[0] == "reset":
        path = save_config({}, config.home)
        click.echo(f"Reset {path}")
        return
    raise click.ClickException(f"Unknown config action: {args[0]}")


def _permissions(config: RuntimeConfig, args: list[str] | None = None) -> None:
    args = args or []
    data = load_config(config.home)
    permissions = data.setdefault("permissions", {})
    action = args[0] if args else "show"
    if action == "show":
        click.echo(json.dumps(permissions, indent=2, ensure_ascii=False))
        return
    if action == "mode":
        if len(args) == 1:
            click.echo(permissions.get("defaultMode", "default"))
            return
        permissions["defaultMode"] = args[1]
        save_config(data, config.home)
        click.echo(f"permissions.defaultMode={args[1]}")
        return
    if action in {"allow", "deny", "ask"}:
        if len(args) < 2:
            raise click.ClickException(f"usage: permissions {action} <tool-pattern> [rule-content]")
        key = f"{action}Rules"
        rules = permissions.setdefault(key, [])
        rules.append({"toolName": args[1], **({"ruleContent": args[2]} if len(args) > 2 else {})})
        save_config(data, config.home)
        click.echo(f"Added {action} rule for {args[1]}")
        return
    if action == "reset":
        data["permissions"] = {}
        save_config(data, config.home)
        click.echo("Reset permissions")
        return
    raise click.ClickException(f"Unknown permissions action: {action}")


def _memory(config: RuntimeConfig, args: list[str] | None = None) -> None:
    args = args or []
    action = args[0] if args else "list"
    if action == "list":
        for path in list_memory_files(config.cwd, config.home):
            exists = "exists" if path.exists() else "missing"
            click.echo(f"{path} [{exists}]")
        return
    if action in {"project", "user"}:
        path = ensure_memory_file(action, config.cwd, config.home)
        click.echo(str(path))
        return
    if action == "edit":
        scope = args[1] if len(args) > 1 else "project"
        path = ensure_memory_file(scope, config.cwd, config.home)
        code = open_in_editor(path)
        if code == -1:
            click.echo(f"No EDITOR/VISUAL configured. Memory file: {path}")
        else:
            click.echo(f"Editor exited with {code}: {path}")
        return
    raise click.ClickException(f"Unknown memory action: {action}")


def _files(config: RuntimeConfig) -> None:
    entries = ReadStateStore().load()
    if not entries:
        click.echo("No files in context")
        return
    for file_path in sorted(entries):
        path = Path(file_path)
        try:
            click.echo(path.relative_to(config.cwd))
        except ValueError:
            click.echo(path)


def _run(config: RuntimeConfig, prompt: str, stream: bool = True) -> None:
    if not prompt.strip():
        raise click.ClickException("usage: run <prompt>")
    try:
        text = run_single_turn(config, prompt, stream=stream)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if not stream:
        click.echo(text)


def get_mcp_servers_info(home: Path, cwd: Path) -> list[dict[str, Any]]:
    from claude_code_py.services.mcp.client import mcp_manager
    from claude_code_py.services.mcp.config import load_mcp_config
    import json

    # Load workspace config
    workspace_path = cwd / ".mcp.json"
    workspace_servers = set()
    if workspace_path.exists():
        try:
            data = json.loads(workspace_path.read_text(encoding="utf-8-sig"))
            workspace_servers = set(data.get("mcpServers", {}).keys())
        except Exception:
            pass

    # Load user config from .frenchie/mcp.json
    from claude_code_py.services.mcp.config import mcp_config_path
    user_config_path = mcp_config_path(home)
    user_servers = set()
    if user_config_path.exists():
        try:
            data = json.loads(user_config_path.read_text(encoding="utf-8-sig"))
            user_servers = set(data.get("mcpServers", {}).keys())
        except Exception:
            pass

    # Group servers
    servers_info = []
    # All loaded config servers:
    configs = load_mcp_config(home, cwd)
    
    # We want to know: scope, name, client status, failure message
    for name, cfg in configs.items():
        scope = "User MCPs"
        scope_path = str(user_config_path)
        if name in workspace_servers:
            scope = "Project MCPs"
            scope_path = str(workspace_path)
        
        from claude_code_py.services.mcp.client import is_mcp_server_disabled
        client = mcp_manager.get_client(name)
        if client and not is_mcp_server_disabled(name, cwd, home):
            status = "connected"
            failure = None
        elif name in mcp_manager.failures:
            status = "failed"
            failure = mcp_manager.failures[name]
        elif is_mcp_server_disabled(name, cwd, home):
            status = "disabled"
            failure = None
        else:
            status = "disabled"
            failure = None
            
        servers_info.append({
            "name": name,
            "scope": scope,
            "scope_path": scope_path,
            "status": status,
            "failure": failure,
        })
    return servers_info


def _arrow_from_char(ch: str) -> str | None:
    """Map a character to an arrow direction."""
    if ch == "A":
        return "up"
    if ch == "B":
        return "down"
    if ch == "C":
        return "right"
    if ch == "D":
        return "left"
    # Windows legacy console codes (after \xe0 prefix)
    if ch == "H":
        return "up"
    if ch == "P":
        return "down"
    if ch == "K":
        return "left"
    if ch == "M":
        return "right"
    return None


def _read_esc_sequence() -> str | None:
    """Read a partial ANSI escape sequence after the initial ESC (\x1b).

    Returns "up", "down", "left", "right" for arrow keys, or ``None``
    if no recognized sequence follows within a short timeout.
    """
    if sys.platform == "win32":
        import msvcrt
        import time

        # On Windows, select.select() doesn't work on stdin.
        # Use msvcrt.kbhit() to check for pending input after ESC.
        deadline = time.monotonic() + 0.05
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                ch2 = msvcrt.getwch()
                if ch2 == "[":
                    # VT/ANSI sequence: ESC [ A/B/C/D (Windows Terminal / modern consoles)
                    time.sleep(0.01)
                    if msvcrt.kbhit():
                        ch3 = msvcrt.getwch()
                        return _arrow_from_char(ch3)
                    return None
                return None
            time.sleep(0.005)
        return None
    else:
        # Unix: use select.select for non-blocking check
        try:
            dr, _, _ = select.select([sys.stdin], [], [], 0.05)
        except Exception:
            return None
        if not dr:
            return None
        try:
            ch2 = click.getchar()
        except Exception:
            return None
        if ch2 == "[":
            try:
                ch3 = click.getchar()
            except Exception:
                return None
            return _arrow_from_char(ch3)
        return None


def get_key() -> str:
    import click

    try:
        ch = click.getchar()
    except (KeyboardInterrupt, SystemExit):
        return "ctrl-c"

    if ch == "\r" or ch == "\n":
        return "enter"
    elif ch == "\x1b":
        # ANSI escape sequence — works in both Unix terminals and Windows bash
        # (Git Bash, MSYS2, Cygwin, WSL, etc.)
        arrow = _read_esc_sequence()
        if arrow is not None:
            return arrow
        return "escape"
    elif ch and ch[0] in ("\x00", "\xe0"):
        # Windows: click.getchar() returns combined \xe0H for arrow keys.
        # The check is on ch[0] because ch may be a 2-char string like \xe0H.
        suffix = ch[1] if len(ch) > 1 else ""
        result = _arrow_from_char(suffix)
        if result:
            return result
        return ch
    elif ch.lower() == "q":
        return "escape"
    return ch


def safe_str(s: str, fallback: str) -> str:
    try:
        encoding = sys.stdout.encoding or "utf-8"
        s.encode(encoding)
        return s
    except Exception:
        return fallback


def render_mcp_menu(servers_info: list[dict[str, Any]], selected_idx: int, expanded_idx: int | None = None) -> Any:
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Group
    
    total_servers = len(servers_info)
    subtitle_text = f"{total_servers} server" if total_servers == 1 else f"{total_servers} servers"
    
    # Group servers by scope
    grouped = {}
    for idx, info in enumerate(servers_info):
        scope = info["scope"]
        scope_path = info["scope_path"]
        heading = f"{scope} ({scope_path})" if scope_path else scope
        grouped.setdefault(heading, []).append((idx, info))
        
    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 0))
    table.add_column()
    
    tick_char = safe_str("✔", "connected")
    cross_char = safe_str("✘", "failed")
    circle_char = safe_str("○", "disabled")
    gear_char = safe_str("⚙", "*")
    bullet_char = safe_str("·", "-")
    pointer_char = safe_str("> ", "> ")
    
    for heading, items in grouped.items():
        table.add_row(f"  [bold white]{heading}[/bold white]")
        for idx, info in items:
            is_selected = (idx == selected_idx)
            ptr = pointer_char if is_selected else "  "
            
            # Status styling
            status = info["status"]
            if status == "connected":
                status_str = f"[bold green]{tick_char}[/bold green]"
                if tick_char == "connected":
                    status_str = f"[bold green]{tick_char}[/bold green]"
                else:
                    status_str = f"[bold green]{tick_char} connected[/bold green]"
            elif status == "failed":
                if cross_char == "failed":
                    status_str = f"[bold red]{cross_char}[/bold red]"
                else:
                    status_str = f"[bold red]{cross_char} failed[/bold red]"
            elif status == "disabled":
                if circle_char == "disabled":
                    status_str = f"[dim]{circle_char}[/dim]"
                else:
                    status_str = f"[dim]{circle_char} disabled[/dim]"
            else:
                status_str = f"[dim]{status}[/dim]"
                
            name_style = "bold #ff8787" if is_selected else "white"
            table.add_row(f"{ptr}[{name_style}]{info['name']}[/{name_style}] [dim]{bullet_char}[/dim] {status_str}")
            
            # If expanded and has failure:
            if idx == expanded_idx and info["failure"]:
                table.add_row(f"    [dim red]Error: {info['failure']}[/dim red]")
        table.add_row("") # spacing
        
    # Footer info
    has_failed = any(info["status"] == "failed" for info in servers_info)
    if has_failed:
        table.add_row(f"  [dim]{gear_char} Run frenchie --debug to see error logs[/dim]")
    table.add_row("  [dim]Configure MCP servers in .mcp.json[/dim]")
    
    panel = Panel(
        table,
        title="[bold #e5484d]Manage MCP servers[/bold #e5484d]",
        subtitle=f"[dim]{subtitle_text}[/dim]",
        title_align="left",
        border_style="#e5484d",
        expand=False,
    )
    
    # Use safe arrow chars for the navigation guide
    nav_guide = safe_str("↑/↓", "Up/Down")
    enter_guide = safe_str("Enter", "Enter")
    esc_guide = safe_str("Esc", "Esc")
    guide = f"\n  [dim]{nav_guide} navigate · {enter_guide} details · + add · Del remove · {esc_guide} cancel[/dim]"
    return Group(panel, guide)


def _mcp_add_interactive(config: RuntimeConfig) -> None:
    """Interactively add a new MCP server to .frenchie/mcp.json."""
    from rich.console import Console
    from rich.panel import Panel
    from claude_code_py.services.mcp.config import add_mcp_server
    console = Console()

    console.print(Panel(
        "[#b0b0b0]Add a new MCP server.[/#b0b0b0]\n"
        "[#6c6c6c]Supports any MCP-compatible server (npx, uvx, python, node, etc.)[/#6c6c6c]",
        title="[bold #e5484d]Add MCP Server[/bold #e5484d]",
        border_style="#e5484d",
    ))

    # 1. Server name
    try:
        server_name = console.input(f"  {safe_str('❯', '>')} Server name (slug, e.g. 'my-tools'): ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    if not server_name:
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    server_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in server_name).lower()

    # Check for collision
    existing = get_mcp_servers_info(config.home, config.cwd)
    if any(s["name"] == server_name for s in existing):
        console.print(f"  [#ff5f5f]✘ Server '{server_name}' already exists.[/#ff5f5f]")
        return

    # 2. Command
    try:
        cmd = console.input(f"  {safe_str('❯', '>')} Command [npx]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    if not cmd:
        cmd = "npx"

    # 3. Arguments (comma-separated)
    try:
        args_str = console.input(
            f"  {safe_str('❯', '>')} Arguments (comma-separated, e.g. '-y,@modelcontextprotocol/server-filesystem'):\n    "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    args_list = [a.strip() for a in args_str.split(",") if a.strip()] if args_str else []

    # 4. Environment variables (optional, comma-separated KEY=VALUE)
    try:
        env_str = console.input(
            f"  {safe_str('❯', '>')} Env vars (optional, comma-separated KEY=VALUE): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    env_dict: dict[str, str] = {}
    if env_str:
        for pair in env_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                env_dict[k.strip()] = v.strip()

    # 5. URL (optional, for HTTP/SSE MCP servers)
    try:
        url = console.input(
            f"  {safe_str('❯', '>')} URL (optional, for HTTP/SSE servers, press Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return

    # Build server config
    server_config: dict[str, Any] = {}
    if url:
        server_config["url"] = url
    else:
        server_config["command"] = cmd
        server_config["args"] = args_list
        if env_dict:
            server_config["env"] = env_dict

    add_mcp_server(server_name, server_config, config.home)
    console.print(f"  [#5fd787]✔[/#5fd787] Server [bold #e5484d]{server_name}[/bold #e5484d] added to .frenchie/mcp.json")
    console.print(f"  [#6c6c6c]Run [bold]/mcp[/bold] to see it in the menu.[/#6c6c6c]")


def run_mcp_interactive_menu(config: RuntimeConfig) -> None:
    # 1. Initialize servers if not already done
    from claude_code_py.services.mcp.client import initialize_mcp_servers
    initialize_mcp_servers(config.home, config.cwd)
    
    # 2. Get server list
    servers_info = get_mcp_servers_info(config.home, config.cwd)
    if not servers_info:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel(
            "  [dim]No MCP servers configured yet.[/dim]\n\n"
            "  [bold #e5484d]/mcp add[/bold #e5484d]  — add a server interactively\n"
            "  [dim]Or create .mcp.json in your project root manually[/dim]",
            title="[bold #e5484d]MCP Servers[/bold #e5484d]",
            border_style="#e5484d",
        ))
        return
        
    selected_idx = 0
    expanded_idx = None
    
    from rich.live import Live
    
    # Hide cursor
    click.echo("\033[?25l", nl=False)
    
    try:
        with Live(render_mcp_menu(servers_info, selected_idx, expanded_idx), auto_refresh=False) as live:
            while True:
                live.update(render_mcp_menu(servers_info, selected_idx, expanded_idx), refresh=True)
                key = get_key()
                
                if key == "ctrl-c" or key == "escape":
                    break
                elif key == "up":
                    selected_idx = (selected_idx - 1) % len(servers_info)
                    expanded_idx = None
                elif key == "down":
                    selected_idx = (selected_idx + 1) % len(servers_info)
                    expanded_idx = None
                elif key == "+" or key.lower() == "a":
                    click.echo("\033[?25h", nl=False)  # show cursor
                    _mcp_add_interactive(config)
                    # Refresh server list
                    servers_info = get_mcp_servers_info(config.home, config.cwd)
                    if not servers_info:
                        break
                    selected_idx = min(selected_idx, len(servers_info) - 1)
                    click.echo("\033[?25l", nl=False)  # hide cursor again
                elif key == "delete":
                    chosen = servers_info[selected_idx]
                    if chosen["scope"] == "User MCPs":
                        from claude_code_py.services.mcp.config import remove_mcp_server
                        removed = remove_mcp_server(chosen["name"], config.home)
                        if removed:
                            click.echo("\033[?25h", nl=False)
                            from rich.console import Console as _Console
                            _Console().print(f"  [#5fd787]✔[/#5fd787] Removed [bold]{chosen['name']}[/bold]")
                        servers_info = get_mcp_servers_info(config.home, config.cwd)
                        if not servers_info:
                            break
                        selected_idx = min(selected_idx, len(servers_info) - 1)
                        click.echo("\033[?25l", nl=False)
                elif key == "enter":
                    if expanded_idx == selected_idx:
                        expanded_idx = None
                    else:
                        if servers_info[selected_idx]["failure"]:
                            expanded_idx = selected_idx
    finally:
        # Show cursor again
        click.echo("\033[?25h", nl=False)


def _mcp(config: RuntimeConfig, args: list[str]) -> None:
    if not args:
        run_mcp_interactive_menu(config)
        return

    action = args[0]

    if action == "add":
        _mcp_add_interactive(config)
        return

    if action == "serve":
        serve_stdio()
        return

    if action in {"enable", "disable"}:
        if len(args) < 2:
            raise click.ClickException(f"usage: mcp {action} <server-name>")
        server_name = args[1]
        
        from claude_code_py.services.mcp.config import load_mcp_config
        configs = load_mcp_config(config.home, config.cwd)
        if server_name not in configs:
            raise click.ClickException(f"Server '{server_name}' is not configured.")
            
        disabled = (action == "disable")
        from claude_code_py.services.mcp.client import set_mcp_server_disabled_state, initialize_mcp_servers, mcp_manager
        
        set_mcp_server_disabled_state(server_name, disabled, config.cwd, config.home)
        
        # Re-initialize MCP servers
        mcp_manager.close_all()
        initialize_mcp_servers(config.home, config.cwd)
        
        state_str = "disabled" if disabled else "enabled"
        click.echo(f"Server '{server_name}' has been {state_str}.")
        return

    # Initialize external MCP servers based on configuration
    from claude_code_py.services.mcp.client import initialize_mcp_servers
    initialize_mcp_servers(config.home, config.cwd)

    explorer = ClaudeCodeExplorer.from_environment()

    if action in {"list", "servers", "status"}:
        from claude_code_py.services.mcp.client import mcp_manager
        servers = []
        for name, client in mcp_manager.clients.items():
            try:
                tools = client.list_tools()
                tool_names = [t["name"] for t in tools]
            except Exception:
                tool_names = []
            
            cmd = getattr(client, "command", "http")
            args_list = getattr(client, "args", [getattr(client, "url", "")])
            
            if client.process is not None:
                is_connected = client.process.poll() is None
            else:
                is_connected = getattr(client, "connected", False)
                
            servers.append({
                "name": name,
                "command": [cmd] + args_list,
                "status": "connected" if is_connected else "disconnected",
                "tools": tool_names
            })
        click.echo(json.dumps(servers, indent=2, ensure_ascii=False))
        return

    if action == "tools":
        all_tools = []
        # Built-in explorer tools
        for t in explorer.list_mcp_tools():
            all_tools.append({
                "server": "frenchie-explorer",
                "name": t["name"],
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema", {})
            })
        # External client tools
        from claude_code_py.services.mcp.client import mcp_manager
        for name, client in mcp_manager.clients.items():
            try:
                for t in client.list_tools():
                    all_tools.append({
                        "server": name,
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "inputSchema": t.get("inputSchema", t.get("schema", {}))
                    })
            except Exception:
                pass
        click.echo(json.dumps(all_tools, indent=2, ensure_ascii=False))
        return

    if action == "call":
        if len(args) < 2:
            raise click.ClickException("usage: mcp call <tool-name> [json-args]")
        tool_name = args[1]
        if len(args) > 2 and args[2].startswith("@"):
            payload = json.loads(Path(args[2][1:]).read_text(encoding="utf-8-sig"))
        else:
            payload = json.loads(args[2]) if len(args) > 2 else {}

        # First, try to call from explorer
        explorer_tool_names = {t["name"] for t in explorer.list_mcp_tools()}
        if tool_name in explorer_tool_names:
            click.echo(json.dumps(explorer.call_tool(tool_name, payload), indent=2, ensure_ascii=False))
            return

        # Then, try to call from external clients
        from claude_code_py.services.mcp.client import mcp_manager
        for name, client in mcp_manager.clients.items():
            try:
                tools = client.list_tools()
                if any(t["name"] == tool_name for t in tools):
                    res = client.call_tool(tool_name, payload)
                    click.echo(json.dumps(res, indent=2, ensure_ascii=False))
                    return
            except Exception:
                pass
        raise click.ClickException(f"Tool '{tool_name}' not found on any active MCP server.")

    if action == "resources":
        lines = []
        # Explorer resources
        lines.append("frenchie-explorer:")
        lines.append("  frenchie://architecture")
        lines.append("  frenchie://tools")
        lines.append("  frenchie://commands")
        # External client resources
        from claude_code_py.services.mcp.client import mcp_manager
        for name, client in mcp_manager.clients.items():
            try:
                res_list = client.list_resources()
                if res_list:
                    lines.append(f"{name}:")
                    for res in res_list:
                        lines.append(f"  {res.get('uri')} ({res.get('name')})")
            except Exception:
                pass
        click.echo("\n".join(lines))
        return

    raise click.ClickException(f"Unknown mcp action: {action}")


def _tools(config: RuntimeConfig) -> None:
    del config
    for tool in tool_registry.names():
        click.echo(tool)


def _tool(config: RuntimeConfig, name: str, payload: dict[str, object]) -> None:
    del config
    tool = tool_registry.get(name)
    try:
        result = tool.call(**payload)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


def _clear(config: RuntimeConfig) -> None:
    from claude_code_py.services.session_store import SessionStore
    from rich.console import Console
    console = Console()
    store = SessionStore(config.home, config.cwd)
    count = 0
    for session_file in store.list_sessions():
        try:
            session_file.unlink()
            count += 1
        except Exception:
            pass
    from claude_code_py.services.cost_tracker import cost_tracker
    cost_tracker.reset()
    cost_tracker.save_to_state(config.home)
    console.print(f"  [#5fd787]✔[/#5fd787] Cleared {count} session(s) and reset cost tracking")


def _exit(config: RuntimeConfig) -> None:
    import sys
    from rich.console import Console
    Console().print(f"  [#e5484d]▸[/#e5484d] [#6c6c6c]Goodbye[#[#6c6c6c]]")
    sys.exit(0)


def _cost(config: RuntimeConfig) -> None:
    from claude_code_py.services.cost_tracker import cost_tracker, format_cost, format_duration, format_number
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    import time
    console = Console()

    cost_tracker.load_from_state(config.home)

    table = Table(box=None, show_header=False, padding=(0, 2), show_edge=False)
    table.add_column(width=22, style="#6c6c6c")
    table.add_column()

    table.add_row("Total cost", f"[bold #5fd787]{format_cost(cost_tracker.total_cost_usd)}[/bold #5fd787]")
    table.add_row("API duration", f"[#b0b0b0]{format_duration(cost_tracker.total_api_duration)}[/#b0b0b0]")
    table.add_row("Wall duration", f"[#b0b0b0]{format_duration(time.time() - cost_tracker.wall_start_time)}[/#b0b0b0]")
    table.add_row("Input tokens", f"[#ff8787]{format_number(cost_tracker.total_input_tokens)}[/#ff8787]")
    table.add_row("Output tokens", f"[#ff8787]{format_number(cost_tracker.total_output_tokens)}[/#ff8787]")
    table.add_row("Cache read", f"[#b0b0b0]{format_number(cost_tracker.total_cache_read_tokens)}[/#b0b0b0]")
    table.add_row("Cache write", f"[#b0b0b0]{format_number(cost_tracker.total_cache_creation_tokens)}[/#b0b0b0]")
    if cost_tracker.web_search_requests > 0:
        table.add_row("Web searches", f"[#ff8787]{cost_tracker.web_search_requests}[/#ff8787]")

    if cost_tracker.model_usage:
        table.add_row("", "")
        for model_name, usage in sorted(cost_tracker.model_usage.items()):
            cost_str = format_cost(usage["cost"])
            tokens = f"{format_number(usage['input'])} in / {format_number(usage['output'])} out"
            table.add_row(f"  {model_name}", f"[#b0b0b0]{tokens}[/#b0b0b0] ([#5fd787]{cost_str}[/#5fd787])")

    panel = Panel(table, title="[bold #e5484d]Session Cost[/bold #e5484d]", border_style="#e5484d", box=box.ROUNDED, expand=False)
    console.print(panel)


def fetch_available_models(config: RuntimeConfig) -> list[dict[str, str]]:
    """Fetch available models from the current provider.

    Returns a list of dicts with 'id', 'name', and optional 'description'.
    For OpenAI-compatible providers (built-in and custom), fetches from /v1/models.
    For Anthropic, returns known Claude models.
    """
    if config.api_provider == "anthropic":
        return [
            {"id": "claude-fable-5", "name": "Claude Fable 5", "description": "Hardest tasks, research, novel architectures"},
            {"id": "claude-opus-4-8", "name": "Claude Opus 4.8", "description": "Complex coding, system design, xhigh effort"},
            {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "description": "Deep reasoning, large refactors"},
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "description": "Extended thinking, multi-file edits"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "description": "Daily coding, balanced speed/quality (default)"},
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5", "description": "Quick edits, iterations, moderate tasks"},
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "description": "Simple queries, autocomplete, tests"},
            {"id": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "description": "Legacy — strong reasoning"},
            {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "description": "Legacy — balanced performance"},
            {"id": "claude-3-5-haiku", "name": "Claude 3.5 Haiku", "description": "Legacy — fast responses"},
            {"id": "claude-3-opus", "name": "Claude 3 Opus", "description": "Legacy — flagship model"},
        ]

    # OpenAI-compatible: built-in (LM Studio) or custom providers
    try:
        from openai import OpenAI
        from claude_code_py.services.config_store import get_config_value
        api_key = get_config_value("api_key", config.home) or "lm-studio"
        base_url = config.api_base_url
        client = OpenAI(api_key=api_key, base_url=base_url)
        raw = client.models.list()
        models = []
        for m in raw:
            mid = m.id
            parts = mid.replace("-", " ").replace("/", " ").split()
            name = " ".join(p.capitalize() for p in parts)
            models.append({"id": mid, "name": name})
        return sorted(models, key=lambda x: x["id"])
    except Exception:
        return []


def _render_model_menu(
    models: list[dict[str, str]],
    selected_idx: int,
    current_model: str,
) -> Any:
    """Render the interactive model picker menu with arrow-key navigation."""
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Group
    from rich import box

    custom_idx = len(models)

    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1))
    table.add_column(width=3, justify="center")
    table.add_column()

    pointer = safe_str("❯", ">")
    dot = safe_str("●", "*")
    ring = safe_str("○", "o")

    for idx, m in enumerate(models):
        is_sel = idx == selected_idx
        is_cur = m["id"] == current_model
        mark = dot if is_cur else ring
        arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if is_sel else " "
        name_style = "bold #e5484d" if is_sel else "#ffffff"
        cur_tag = f" [#5fd787]{safe_str('✔', '[ok]')} current[/#5fd787]" if is_cur else ""
        desc = m.get("description", "")

        line = f"[{name_style}]{mark} {m['name']}[/{name_style}]{cur_tag}\n   [#6c6c6c]{m['id']}[/#6c6c6c]"
        if desc:
            line += f"\n   [#6c6c6c]{desc}[/#6c6c6c]"
        table.add_row(arrow, line)

    # Custom model option
    table.add_row("")
    is_custom_sel = selected_idx == custom_idx
    custom_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if is_custom_sel else " "
    custom_style = "bold #5fd787" if is_custom_sel else "#5fd787"
    custom_label = safe_str("+", "+")
    table.add_row(custom_arrow, f"[{custom_style}]{custom_label} Custom model...[/{custom_style}]")

    panel = Panel(
        table,
        title="[bold #e5484d]Select Model[/bold #e5484d]",
        border_style="#e5484d",
        box=box.ROUNDED,
        expand=False,
        padding=(0, 1),
    )

    nav = safe_str("↑/↓", "Up/Down")
    guide = (
        f"\n  [dim]{nav} navigate · Enter select · "
        f"+ custom · Esc cancel[/dim]"
    )
    return Group(panel, guide)


def _apply_model(config: RuntimeConfig, model_id: str) -> None:
    """Persist the selected model and print a confirmation."""
    from rich.console import Console
    from claude_code_py.services.config_store import KEY_MODEL, set_config_value
    console = Console()
    set_config_value(KEY_MODEL, model_id, config.home)
    console.print(f"  [#5fd787]{safe_str('✔', '[ok]')}[/#5fd787] Model set to [bold #e5484d]{model_id}[/bold #e5484d]")
    console.print("  [#6c6c6c]Restart chat to use the new model.[/#6c6c6c]")


def run_model_interactive_menu(config: RuntimeConfig) -> None:
    """Interactive model picker with arrow-key navigation."""
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    console = Console()

    # Fetch available models
    with console.status("[bold #e5484d]Fetching models...[/bold #e5484d]"):
        models = fetch_available_models(config)

    current_model = config.model

    if not models:
        # Can't fetch — prompt for custom ID directly
        console.print(Panel(
            "[#b0b0b0]Could not fetch models from provider.[/#b0b0b0]\n"
            "[#6c6c6c]Enter a model ID manually.[/#6c6c6c]",
            title="[bold #e5484d]Select Model[/bold #e5484d]",
            border_style="#e5484d",
        ))
        custom_model = console.input(f"  {safe_str('❯', '>')} Model ID [{current_model}]: ").strip()
        if not custom_model:
            custom_model = current_model
        _apply_model(config, custom_model)
        return

    selected_idx = next(
        (i for i, m in enumerate(models) if m["id"] == current_model), 0
    )
    custom_idx = len(models)

    click.echo("\033[?25l", nl=False)  # hide cursor
    try:
        with Live(_render_model_menu(models, selected_idx, current_model), auto_refresh=False) as live:
            while True:
                total_items = custom_idx + 1
                live.update(_render_model_menu(models, selected_idx, current_model), refresh=True)
                key = get_key()

                if key in ("ctrl-c", "escape"):
                    console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
                    return
                elif key == "up":
                    selected_idx = (selected_idx - 1) % total_items
                elif key == "down":
                    selected_idx = (selected_idx + 1) % total_items
                elif key == "+" or key.lower() == "c":
                    # Custom model prompt
                    click.echo("\033[?25h", nl=False)
                    console.print(Panel(
                        "[#b0b0b0]Enter any model ID supported by your provider.[/#b0b0b0]",
                        title="[bold #e5484d]Custom Model[/bold #e5484d]",
                        border_style="#e5484d",
                    ))
                    custom_model = console.input(f"  {safe_str('❯', '>')} Model ID: ").strip()
                    if custom_model:
                        _apply_model(config, custom_model)
                    else:
                        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
                    return
                elif key == "enter":
                    if selected_idx == custom_idx:
                        # "Custom model..." row selected
                        click.echo("\033[?25h", nl=False)
                        console.print(Panel(
                            "[#b0b0b0]Enter any model ID supported by your provider.[/#b0b0b0]",
                            title="[bold #e5484d]Custom Model[/bold #e5484d]",
                            border_style="#e5484d",
                        ))
                        custom_model = console.input(f"  {safe_str('❯', '>')} Model ID: ").strip()
                        if custom_model:
                            _apply_model(config, custom_model)
                        else:
                            console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
                        return
                    else:
                        chosen = models[selected_idx]["id"]
                        _apply_model(config, chosen)
                        return
    finally:
        click.echo("\033[?25h", nl=False)  # show cursor


def _model(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Show or set the active model. Without args, opens an interactive picker."""
    args = args or []
    from rich.console import Console
    console = Console()

    if not args:
        run_model_interactive_menu(config)
        return

    model_val = args[1] if args[0] == "set" and len(args) > 1 else args[0]
    _apply_model(config, model_val)


# Built-in provider options.
_BUILTIN_PROVIDERS = [
    {
        "id": "openai",
        "title": "LM Studio (local)",
        "hint": "OpenAI-compatible server, no API key needed",
    },
    {
        "id": "anthropic",
        "title": "Anthropic API",
        "hint": "Cloud Claude models, requires an API key (/login)",
    },
]


def _get_all_provider_options(home) -> list[dict[str, Any]]:
    """Return built-in + custom providers merged into one list."""
    from claude_code_py.services.config_store import load_providers
    custom = load_providers(home)
    options = list(_BUILTIN_PROVIDERS)
    for cp in custom:
        options.append({
            "id": cp["id"],
            "title": cp.get("title", cp["id"]),
            "hint": cp.get("base_url", ""),
            "_custom": True,
            "_base_url": cp.get("base_url", ""),
            "_api_key": cp.get("api_key", ""),
            "_default_model": cp.get("default_model", ""),
        })
    return options


def _render_provider_menu(selected_idx: int, current: str, options: list[dict[str, Any]]):
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Group
    from rich import box

    has_custom = any(opt.get("_custom") for opt in options)
    add_idx = len(options)
    remove_idx = add_idx + 1 if has_custom else None

    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1))
    table.add_column(width=3, justify="center")
    table.add_column()

    pointer = safe_str("❯", ">")
    dot = safe_str("●", "*")
    ring = safe_str("○", "o")
    for idx, opt in enumerate(options):
        is_sel = idx == selected_idx
        is_cur = opt["id"] == current
        mark = dot if is_cur else ring
        arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if is_sel else " "
        name_style = "bold #e5484d" if is_sel else "#ffffff"
        cur_tag = " [#5fd787](current)[/#5fd787]" if is_cur else ""
        custom_tag = " [#ffd75f](custom)[/#ffd75f]" if opt.get("_custom") else ""
        table.add_row(
            arrow,
            f"[{name_style}]{mark} {opt['title']}[/{name_style}]{cur_tag}{custom_tag}\n"
            f"   [#6c6c6c]{opt['hint']}[/#6c6c6c]",
        )

    # Footer actions
    table.add_row("")
    add_label = safe_str("+", "+")
    add_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if selected_idx == add_idx else " "
    add_style = "bold #5fd787" if selected_idx == add_idx else "#5fd787"
    table.add_row(add_arrow, f"[{add_style}]{add_label} Add custom provider...[/{add_style}]")

    if has_custom:
        remove_label = safe_str("-", "-")
        remove_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if selected_idx == remove_idx else " "
        remove_style = "bold #ff5f5f" if selected_idx == remove_idx else "#ff5f5f"
        table.add_row(remove_arrow, f"[{remove_style}]{remove_label} Remove custom provider...[/{remove_style}]")

    panel = Panel(
        table,
        title="[bold #e5484d]Select API provider[/bold #e5484d]",
        border_style="#e5484d",
        box=box.ROUNDED,
        expand=False,
        padding=(0, 1),
    )
    nav = safe_str("↑/↓", "Up/Down")
    guide = f"\n  [dim]{nav} to navigate · Enter to select · + to add · - to remove · Esc to cancel[/dim]"
    return Group(panel, guide)


def _provider_add_interactive(config: RuntimeConfig) -> None:
    """Interactively add a new custom OpenAI-compatible provider."""
    from rich.console import Console
    from rich.panel import Panel
    from claude_code_py.services.config_store import add_custom_provider
    console = Console()

    console.print(Panel(
        "[#b0b0b0]Add a custom OpenAI-compatible provider.[/#b0b0b0]\n"
        "[#6c6c6c]Any server that implements the OpenAI API (vLLM, Ollama, LiteLLM, etc.)[/#6c6c6c]",
        title="[bold #e5484d]Add Provider[/bold #e5484d]",
        border_style="#e5484d",
    ))

    # 1. Short id (slug)
    try:
        provider_id = console.input(f"  {safe_str('❯', '>')} Provider ID (slug, e.g. 'vllm'): ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    if not provider_id:
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    provider_id = "".join(c if c.isalnum() or c in "-_" else "-" for c in provider_id).lower()

    # Check for id collision
    existing = _get_all_provider_options(config.home)
    if any(o["id"] == provider_id for o in existing):
        console.print(f"  [#ff5f5f]✘ Provider '{provider_id}' already exists.[/#ff5f5f]")
        return

    # 2. Display title
    try:
        title = console.input(f"  {safe_str('❯', '>')} Display name [{provider_id}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return
    if not title:
        title = provider_id

    # 3. Base URL
    default_url = "http://localhost:8000/v1"
    try:
        base_url = console.input(
            f"  {safe_str('❯', '>')} Base URL [{default_url}]: "
        ).strip() or default_url
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return

    # 4. API key (optional)
    try:
        api_key = console.input(
            f"  {safe_str('❯', '>')} API key (optional, press Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return

    # 5. Default model (optional)
    try:
        default_model = console.input(
            f"  {safe_str('❯', '>')} Default model (optional, press Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
        return

    provider: dict[str, Any] = {
        "id": provider_id,
        "title": title,
        "base_url": base_url,
    }
    if api_key:
        provider["api_key"] = api_key
    if default_model:
        provider["default_model"] = default_model

    add_custom_provider(provider, config.home)
    console.print(f"  [#5fd787]✔[/#5fd787] Provider [bold #e5484d]{title}[/bold #e5484d] added.")
    console.print(f"  [#6c6c6c]Select it with [bold]/provider[/bold] to activate.[/#6c6c6c]")


def _provider_remove_interactive(config: RuntimeConfig) -> None:
    """Interactively remove a custom provider with arrow-key navigation."""
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from claude_code_py.services.config_store import load_providers, remove_custom_provider

    console = Console()
    custom = load_providers(config.home)
    if not custom:
        console.print("  [#6c6c6c]No custom providers to remove.[/#6c6c6c]")
        return

    pointer = safe_str("❯", ">")

    def renderRemoveMenu(sel_idx: int, confirm_idx: int | None = None):
        table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1))
        table.add_column(width=3, justify="center")
        table.add_column()
        for i, cp in enumerate(custom):
            is_sel = i == sel_idx and confirm_idx is None
            arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if is_sel else " "
            style = "bold #e5484d" if is_sel else "#ffffff"
            table.add_row(
                arrow,
                f"[{style}]{i+1}. {cp.get('title', cp['id'])}[/{style}]\n"
                f"   [#6c6c6c]{cp.get('base_url', '')}[/#6c6c6c]",
            )
        table.add_row("")
        cancel_sel = confirm_idx == 0
        cancel_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if cancel_sel else " "
        cancel_style = "bold #6c6c6c" if cancel_sel else "#6c6c6c"
        table.add_row(cancel_arrow, f"[{cancel_style}]Cancel[/{cancel_style}]")

        if confirm_idx is not None:
            table.add_row("")
            yes_sel = confirm_idx == 1
            no_sel = confirm_idx == 2
            yes_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if yes_sel else " "
            no_arrow = f"[bold #e5484d]{pointer}[/bold #e5484d]" if no_sel else " "
            yes_style = "bold #ff5f5f" if yes_sel else "#ff5f5f"
            no_style = "bold #6c6c6c" if no_sel else "#6c6c6c"
            table.add_row(yes_arrow, f"[{yes_style}]Yes, remove {custom[sel_idx].get('title', custom[sel_idx]['id'])}[/{yes_style}]")
            table.add_row(no_arrow, f"[{no_style}]No, go back[/{no_style}]")

        panel = Panel(
            table,
            title="[bold #e5484d]Remove Provider[/bold #e5484d]",
            border_style="#e5484d",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 1),
        )
        nav = safe_str("↑/↓", "Up/Down")
        if confirm_idx is None:
            guide = f"\n  [dim]{nav} to navigate · Enter to select · Esc to cancel[/dim]"
        else:
            guide = f"\n  [dim]{nav} to navigate · Enter to confirm · Esc to cancel[/dim]"
        return Group(panel, guide)

    from rich.live import Live
    sel_idx = 0
    confirm_idx = None  # None = provider list, 0 = cancel, 1 = yes, 2 = no
    click.echo("\033[?25l", nl=False)
    try:
        with Live(renderRemoveMenu(sel_idx, confirm_idx), auto_refresh=False) as live:
            while True:
                live.update(renderRemoveMenu(sel_idx, confirm_idx), refresh=True)
                key = get_key()
                if key in ("ctrl-c", "escape"):
                    console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
                    return
                if confirm_idx is None:
                    total = len(custom) + 1
                    if key == "up":
                        sel_idx = (sel_idx - 1) % total
                    elif key == "down":
                        sel_idx = (sel_idx + 1) % total
                    elif key == "enter":
                        if sel_idx == len(custom):
                            return  # Cancel
                        confirm_idx = 1  # move to confirmation
                else:
                    if key == "up":
                        confirm_idx = (confirm_idx - 1) % 3
                    elif key == "down":
                        confirm_idx = (confirm_idx + 1) % 3
                    elif key == "enter":
                        if confirm_idx == 0:
                            confirm_idx = None  # back to list
                        elif confirm_idx == 1:
                            target = custom[sel_idx]
                            removed = remove_custom_provider(target["id"], config.home)
                            if removed:
                                console.print(f"  [#5fd787]✔[/#5fd787] Removed [bold]{target.get('title', target['id'])}[/bold]")
                            return
                        else:
                            confirm_idx = None  # back to list
    finally:
        click.echo("\033[?25h", nl=False)


def _provider(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Pick the API provider from an interactive menu and persist it."""
    args = args or []
    from rich.console import Console
    from claude_code_py.services.config_store import (
        KEY_API_KEY,
        KEY_BASE_URL,
        KEY_MODEL,
        KEY_PROVIDER,
        DEFAULT_SETTINGS,
        set_config_value,
        load_providers,
    )
    console = Console()

    # /provider add — interactive add custom provider
    if args and args[0] == "add":
        _provider_add_interactive(config)
        return

    # /provider remove — interactive remove custom provider
    if args and args[0] == "remove":
        _provider_remove_interactive(config)
        return

    # Build the full options list (built-in + custom)
    options = _get_all_provider_options(config.home)

    # Allow non-interactive use: /provider openai | anthropic | lm-studio | <custom-id>
    chosen = None
    chosen_custom: dict[str, Any] | None = None
    if args:
        raw = args[0].lower()
        alias = {"lm-studio": "openai", "lmstudio": "openai", "local": "openai", "claude": "anthropic"}
        raw = alias.get(raw, raw)
        if raw in {opt["id"] for opt in options}:
            chosen = raw
            for opt in options:
                if opt["id"] == raw and opt.get("_custom"):
                    chosen_custom = opt
                    break
        else:
            raise click.ClickException(f"Unknown provider: {args[0]}")

    if chosen is None:
        current = config.api_provider
        selected_idx = next(
            (i for i, o in enumerate(options) if o["id"] == current), 0
        )
        from rich.live import Live
        click.echo("\033[?25l", nl=False)  # hide cursor
        try:
            with Live(_render_provider_menu(selected_idx, current, options), auto_refresh=False) as live:
                while True:
                    has_custom = any(opt.get("_custom") for opt in options)
                    add_idx = len(options)
                    remove_idx = add_idx + 1 if has_custom else None
                    total_items = remove_idx + 1 if remove_idx is not None else add_idx + 1
                    live.update(_render_provider_menu(selected_idx, current, options), refresh=True)
                    key = get_key()
                    if key in ("ctrl-c", "escape"):
                        console.print("  [#6c6c6c]Cancelled.[/#6c6c6c]")
                        return
                    elif key == "up":
                        selected_idx = (selected_idx - 1) % total_items
                    elif key == "down":
                        selected_idx = (selected_idx + 1) % total_items
                    elif key == "+" or key.lower() == "a":
                        click.echo("\033[?25h", nl=False)
                        _provider_add_interactive(config)
                        options = _get_all_provider_options(config.home)
                        selected_idx = min(selected_idx, len(options))
                        click.echo("\033[?25l", nl=False)
                    elif key in ("-", "delete"):
                        if selected_idx < len(options) and options[selected_idx].get("_custom"):
                            click.echo("\033[?25h", nl=False)
                            _provider_remove_interactive(config)
                            options = _get_all_provider_options(config.home)
                            selected_idx = min(selected_idx, len(options) - 1)
                            click.echo("\033[?25l", nl=False)
                    elif key == "enter":
                        if selected_idx == add_idx:
                            click.echo("\033[?25h", nl=False)
                            _provider_add_interactive(config)
                            options = _get_all_provider_options(config.home)
                            selected_idx = min(selected_idx, len(options))
                            click.echo("\033[?25l", nl=False)
                        elif remove_idx is not None and selected_idx == remove_idx:
                            click.echo("\033[?25h", nl=False)
                            _provider_remove_interactive(config)
                            options = _get_all_provider_options(config.home)
                            selected_idx = min(selected_idx, len(options) - 1)
                            click.echo("\033[?25l", nl=False)
                        else:
                            chosen = options[selected_idx]["id"]
                            if options[selected_idx].get("_custom"):
                                chosen_custom = options[selected_idx]
                            break
        finally:
            click.echo("\033[?25h", nl=False)  # show cursor

    # Persist the choice.
    set_config_value(KEY_PROVIDER, chosen, config.home)

    # If it's a custom provider, apply its base_url and api_key.
    if chosen_custom:
        base_url = chosen_custom.get("_base_url")
        if base_url:
            set_config_value(KEY_BASE_URL, base_url, config.home)
        api_key = chosen_custom.get("_api_key")
        if api_key:
            set_config_value(KEY_API_KEY, api_key, config.home)
        default_model = chosen_custom.get("_default_model")
        if default_model:
            set_config_value(KEY_MODEL, default_model, config.home)
        console.print(
            f"  [#5fd787]✔[/#5fd787] Provider set to [bold #e5484d]{chosen_custom.get('title', chosen)}[/bold #e5484d] "
            f"[#6c6c6c]({base_url})[/#6c6c6c]"
        )
        if default_model:
            console.print(
                f"  [#6c6c6c]Model set to [bold]{default_model}[/bold][/#6c6c6c]"
            )
    elif chosen == "openai":
        default_url = config.api_base_url or DEFAULT_SETTINGS[KEY_BASE_URL]
        try:
            url = console.input(
                f"  [#e5484d]{safe_str('❯', '>')}[/#e5484d] Base URL [#6c6c6c]({default_url})[/#6c6c6c]: "
            ).strip() or default_url
        except (EOFError, KeyboardInterrupt):
            url = default_url
        set_config_value(KEY_BASE_URL, url, config.home)
        from claude_code_py.services.config_store import get_config_value
        if not get_config_value(KEY_API_KEY, config.home):
            set_config_value(KEY_API_KEY, "lm-studio", config.home)
        console.print(
            f"  [#5fd787]✔[/#5fd787] Provider set to [bold #e5484d]LM Studio[/bold #e5484d] "
            f"[#6c6c6c]({url})[/#6c6c6c]"
        )
        console.print(
            f"  [#6c6c6c]Tip: set the model with [bold]/model <id>[/bold] "
            f"to match what's loaded in LM Studio.[/#6c6c6c]"
        )
    else:
        console.print(
            f"  [#5fd787]✔[/#5fd787] Provider set to [bold #e5484d]Anthropic[/bold #e5484d]"
        )
        from claude_code_py.services.auth import check_auth_status
        if check_auth_status(config.home)["status"] != "authenticated":
            console.print(
                f"  [#ffd75f]{safe_str('⚠', '!')}[/#ffd75f] No API key found — run [bold]/login[/bold] to add one."
            )

    console.print("  [#6c6c6c]Applied to this session.[/#6c6c6c]")


def _compact(config: RuntimeConfig) -> None:
    from claude_code_py.services.session_store import SessionStore
    from rich.console import Console
    console = Console()
    store = SessionStore(config.home, config.cwd)
    sessions = store.list_sessions()
    if not sessions:
        console.print(f"  [#6c6c6c]No session to compact.[/#6c6c6c]")
        return
    latest_session_path = sessions[0]
    if latest_session_path.exists():
        try:
            lines = latest_session_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 6:
                compacted = lines[-4:]
                latest_session_path.write_text("\n".join(compacted) + "\n", encoding="utf-8")
                console.print(f"  [#5fd787]✔[/#5fd787] Compacted history (kept last {len(compacted)} messages)")
            else:
                console.print(f"  [#6c6c6c]Conversation is already compact.[/#6c6c6c]")
        except Exception as e:
            from rich.markup import escape as _esc
            console.print(f"  [#ff5f5f]✘[/#ff5f5f] Failed to compact: {_esc(str(e))}")


def _execute_shell_commands_in_prompt(prompt: str) -> str:
    import re
    import subprocess
    pattern = r"!\`([^\`]+)\`"
    def replacer(match: re.Match) -> str:
        cmd = match.group(1)
        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                text=True,
                capture_output=True,
            )
            return completed.stdout.strip()
        except Exception as exc:
            return f"Error executing '{cmd}': {exc}"
    return re.sub(pattern, replacer, prompt)


def _commit(config: RuntimeConfig) -> None:
    prompt_template = """## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`

## Git Safety Protocol

- NEVER update the git config
- NEVER skip hooks (--no-verify, --no-gpg-sign, etc) unless the user explicitly requests it
- CRITICAL: ALWAYS create NEW commits. NEVER use git commit --amend, unless the user explicitly requests it
- Do not commit files that likely contain secrets (.env, credentials.json, etc). Warn the user if they specifically request to commit those files
- If there are no changes to commit (i.e., no untracked files and no modifications), do not create an empty commit
- Never use git commands with the -i flag (like git rebase -i or git add -i) since they require interactive input which is not supported

## Your task

Based on the above changes, create a single git commit:

1. Analyze all staged changes and draft a commit message:
   - Look at the recent commits above to follow this repository's commit message style
   - Summarize the nature of the changes (new feature, enhancement, bug fix, refactoring, test, docs, etc.)
   - Ensure the message accurately reflects the changes and their purpose (i.e. "add" means a wholly new feature, "update" means an enhancement to an existing feature, "fix" means a bug fix, etc.)
   - Draft a concise (1-2 sentences) commit message that focuses on the "why" rather than the "what"

2. Stage relevant files and create the commit using HEREDOC syntax:
```
git commit -m "$(cat <<'EOF'
Commit message here.
EOF
)"
```

You have the capability to call multiple tools in a single response. Stage and create the commit using a single message. Do not use any other tools or do anything else. Do not send any other text or messages besides these tool calls."""
    prompt = _execute_shell_commands_in_prompt(prompt_template)
    try:
        run_single_turn(config, prompt, stream=True)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _init(config: RuntimeConfig) -> None:
    prompt = """Please analyze this codebase and create a FRENCHIE.md file, which will be given to future instances of Frenchie to operate in this repository.

What to add:
1. Commands that will be commonly used, such as how to build, lint, and run tests. Include the necessary commands to develop in this codebase, such as how to run a single test.
2. High-level code architecture and structure so that future instances can be productive more quickly. Focus on the "big picture" architecture that requires reading multiple files to understand.

Usage notes:
- If there's already a FRENCHIE.md, suggest improvements to it.
- When you make the initial FRENCHIE.md, do not repeat yourself and do not include obvious instructions like "Provide helpful error messages to users", "Write unit tests for all new utilities", "Never include sensitive information (API keys, tokens) in code or commits".
- Avoid listing every component or file structure that can be easily discovered.
- Don't include generic development practices.
- If there are Cursor rules (in .cursor/rules/ or .cursorrules) or Copilot rules (in .github/copilot-instructions.md), make sure to include the important parts.
- If there is a README.md, make sure to include the important parts.
- Do not make up information such as "Common Development Tasks", "Tips for Development", "Support and Documentation" unless this is expressly included in other files that you read.
- Be sure to prefix the file with the following text:

```
# FRENCHIE.md

This file provides guidance to Frenchie when working with code in this repository.
```"""
    try:
        run_single_turn(config, prompt, stream=True)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def _version(config: RuntimeConfig) -> None:
    from claude_code_py import __version__
    from rich.console import Console
    Console().print(f"[bold #e5484d]Frenchie[/bold #e5484d] [dim]v{__version__}[/dim]")


def _login(config: RuntimeConfig) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich import box
    console = Console()
    console.print(Panel(
        "[#b0b0b0]Save an API key for the Anthropic provider.[/#b0b0b0]\n"
        "[#6c6c6c]Not needed for the local LM Studio provider (see /provider).[/#6c6c6c]",
        title=f"[bold #e5484d]Login[/bold #e5484d]",
        border_style="#e5484d", box=box.ROUNDED, expand=False,
    ))
    api_key = click.prompt("  Enter your API key", hide_input=True).strip()
    if not api_key:
        console.print(f"  [#6c6c6c]Login cancelled.[/#6c6c6c]")
        return

    from claude_code_py.services.auth import login_user
    with console.status("[bold #e5484d]Verifying...[/bold #e5484d]"):
        success = login_user(api_key, config.home)
    if success:
        console.print(f"  [#5fd787]✔[/#5fd787] Login successful, key saved")
    else:
        console.print(f"  [#ff5f5f]✘[/#ff5f5f] Authentication failed. Check your API key.")


def _logout(config: RuntimeConfig) -> None:
    from claude_code_py.services.auth import logout_user
    from rich.console import Console
    logout_user(config.home)
    Console().print(f"  [#5fd787]✔[/#5fd787] Logged out, local API key cleared")


def _bridge(config: RuntimeConfig, args: list[str] | None = None) -> None:
    args = args or []
    port = 54321
    if args:
        try:
            port = int(args[0])
        except ValueError:
            raise click.ClickException("usage: bridge [port]")

    click.echo(f"Starting IDE Bridge server on port {port}...")
    from claude_code_py.services.bridge import BridgeServer
    import asyncio

    server = BridgeServer(port=port)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.start())
        click.echo("Bridge server is running. Press Ctrl+C to stop.")
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        click.echo("\nStopping bridge server...")
        loop.run_until_complete(server.stop())
    finally:
        loop.close()


def _web(config: RuntimeConfig, args: list[str] | None = None) -> None:
    args = args or []
    port = 3001
    if args:
        try:
            port = int(args[0])
        except ValueError:
            raise click.ClickException("usage: web [port]")

    click.echo(f"Starting Web Visualization Dashboard backend on http://localhost:{port}...")
    import uvicorn

    uvicorn.run("claude_code_py.services.web_server:app", host="127.0.0.1", port=port, log_level="info")


command_registry.register("help", _help, "Show help and available commands")
command_registry.register("doctor", _doctor, "Diagnose and verify installation and settings")
command_registry.register("status", _status, "Show status including model, config, and tools")
command_registry.register("config", _config, "Show or edit config", aliases=("settings",))
command_registry.register("permissions", _permissions, "Manage allow and deny tool permission rules", aliases=("allowed-tools",))
command_registry.register("memory", _memory, "List, create, or edit memory files")
command_registry.register("files", _files, "List files currently available in context")
command_registry.register("run", _run, "Run a single prompt through the model")
command_registry.register("mcp", _mcp, "MCP command scaffold")
command_registry.register("tools", _tools, "List available tools")
command_registry.register("tool", _tool, "Execute a tool by name")
command_registry.register("clear", _clear, "Clear conversation history and free up context", aliases=("reset", "new"))
command_registry.register("exit", _exit, "Exit the tool")
command_registry.register("cost", _cost, "Show the total cost and duration of the current session")
command_registry.register("compact", _compact, "Compact conversation history")
command_registry.register("model", _model, "Show or override the active model setting")
command_registry.register("commit", _commit, "Create a git commit")
command_registry.register("init", _init, "Initialize FRENCHIE.md file with codebase documentation")
command_registry.register("provider", _provider, "Switch API provider, add/remove custom providers")
command_registry.register("version", _version, "Print version")
command_registry.register("login", _login, "Save an API key for the Anthropic provider")
command_registry.register("logout", _logout, "Log out and clear active authentication credentials")
command_registry.register("bridge", _bridge, "Start local IDE WebSocket bridge server", aliases=("remote-control",))
command_registry.register("web", _web, "Start Web Visualization Dashboard backend", aliases=("desktop",))



def _cd(config: RuntimeConfig, path: str | None = None) -> None:
    import os
    if not path:
        click.echo(f"Current directory: {config.cwd}")
        return
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise click.ClickException(f"Path does not exist: {target}")
    if not target.is_dir():
        raise click.ClickException(f"Not a directory: {target}")
    os.chdir(target)
    click.echo(f"Changed directory to: {target}")


def _usage(config: RuntimeConfig) -> None:
    from claude_code_py.services.cost_tracker import cost_tracker, format_cost, format_duration, format_number
    cost_tracker.load_from_state(config.home)

    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 2))
    table.add_column(width=22, style="dim")
    table.add_column()

    table.add_row("Total cost", f"[bold green]{format_cost(cost_tracker.total_cost_usd)}[/bold green]")
    table.add_row("API duration", format_duration(cost_tracker.total_api_duration))
    table.add_row("Wall duration", format_duration(time.time() - cost_tracker.wall_start_time))
    table.add_row("Input tokens", f"[cyan]{format_number(cost_tracker.total_input_tokens)}[/cyan]")
    table.add_row("Output tokens", f"[cyan]{format_number(cost_tracker.total_output_tokens)}[/cyan]")
    table.add_row("Cache read", format_number(cost_tracker.total_cache_read_tokens))
    table.add_row("Cache write", format_number(cost_tracker.total_cache_creation_tokens))
    table.add_row("Web searches", str(cost_tracker.web_search_requests))

    if cost_tracker.model_usage:
        table.add_row("", "")
        table.add_row("[bold]Model breakdown[/bold]", "")
        for model_name, usage in sorted(cost_tracker.model_usage.items()):
            cost = format_cost(usage["cost"])
            tokens = f"{format_number(usage['input'])} in / {format_number(usage['output'])} out"
            table.add_row(f"  {model_name}", f"{tokens} ({cost})")

    panel = Panel(table, title="[bold #e5484d]Session Usage[/bold #e5484d]", border_style="#e5484d", expand=False)
    console.print(panel)


def _diff(config: RuntimeConfig) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(config.cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise click.ClickException(f"git diff failed: {result.stderr.strip()}")
        if not result.stdout.strip():
            click.echo("No changes to show.")
            return
        from rich.console import Console
        from rich.syntax import Syntax
        console = Console()
        syntax = Syntax(result.stdout, "diff", theme="monokai", line_numbers=False)
        console.print(syntax)
    except FileNotFoundError:
        raise click.ClickException("git is not installed or not in PATH")
    except Exception as exc:
        raise click.ClickException(str(exc))


def _code_review(config: RuntimeConfig) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(config.cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if not result.stdout.strip():
            click.echo("No changes to review.")
            return
        prompt = f"""Review the following code changes for correctness bugs, security issues, and style problems. Be concise and direct.

```
{result.stdout[:10000]}
```

Focus on:
1. Correctness bugs
2. Security vulnerabilities  
3. Performance issues
4. Style improvements

Report findings as a bullet list. If no issues found, say "No issues found."
"""
        run_single_turn(config, prompt, stream=True)
    except Exception as exc:
        raise click.ClickException(str(exc))


def _resume(config: RuntimeConfig, args: list[str] | None = None) -> None:
    from claude_code_py.services.session_store import SessionStore
    store = SessionStore(config.home, config.cwd)
    sessions = store.list_sessions()
    if not sessions:
        click.echo("No previous sessions found.")
        return
    click.echo("Recent sessions:")
    for i, session_path in enumerate(sessions[:10]):
        try:
            lines = session_path.read_text(encoding="utf-8").splitlines()
            first_msg = ""
            for line in lines:
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            first_msg = content[:80]
                        break
                except Exception:
                    continue
            size = session_path.stat().st_size
            click.echo(f"  [{i+1}] {session_path.name} ({size}B) - {first_msg}")
        except Exception:
            click.echo(f"  [{i+1}] {session_path.name}")
    if args and args[0]:
        try:
            idx = int(args[0]) - 1
            if 0 <= idx < len(sessions):
                click.echo(f"Resuming session: {sessions[idx].name}")
                # Load session messages and continue
                store.current_session = sessions[idx]
                click.echo("Session loaded. Continue chatting in the REPL.")
        except (ValueError, IndexError):
            raise click.ClickException(f"Invalid session index: {args[0]}")


def _agents(config: RuntimeConfig, args: list[str] | None = None) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()

    from claude_code_py.services.cost_tracker import cost_tracker
    cost_tracker.load_from_state(config.home)

    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 2))
    table.add_column(width=20, style="dim")
    table.add_column()

    table.add_row("Active model", f"[bold #e5484d]{config.model}[/bold #e5484d]")
    table.add_row("Working directory", str(config.cwd))
    table.add_row("Session cost", f"[green]${cost_tracker.total_cost_usd:.4f}[/green]")
    table.add_row("Tokens used", f"{cost_tracker.total_input_tokens + cost_tracker.total_output_tokens:,}")

    from claude_code_py.services.auth import check_auth_status
    auth = check_auth_status(config.home)
    table.add_row("Auth", f"Authenticated ({auth['source']})" if auth["status"] == "authenticated" else "Not authenticated")

    from claude_code_py.services.mcp.client import mcp_manager
    table.add_row("MCP servers", f"{len(mcp_manager.clients)} connected")

    panel = Panel(table, title="[bold #e5484d]Agent Status[/bold #e5484d]", border_style="#e5484d", expand=False)
    console.print(panel)


command_registry.register("cd", _cd, "Change working directory within the session")
command_registry.register("usage", _usage, "Show detailed token usage breakdown")
command_registry.register("diff", _diff, "Show git diff of current changes")
command_registry.register("code-review", _code_review, "Review current changes for bugs and issues")
command_registry.register("resume", _resume, "Resume a previous session")
command_registry.register("agents", _agents, "Show agent status and running sessions")


def _advisor(config: RuntimeConfig, args: list[str] | None = None) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()

    table = Table(show_header=True, header_style="bold #e5484d", padding=(0, 2))
    table.add_column("Model", style="bold")
    table.add_column("Tier")
    table.add_column("Best For")
    table.add_column("Cost", justify="right")

    models = [
        ("claude-fable-5", "Mythos", "Hardest tasks, research, novel architectures", "$$$"),
        ("claude-opus-4-8", "Flagship", "Complex coding, system design, xhigh effort", "$$$"),
        ("claude-opus-4-7", "Flagship", "Deep reasoning, large refactors", "$$$"),
        ("claude-opus-4-6", "Flagship", "Extended thinking, multi-file edits", "$$$"),
        ("claude-sonnet-4-6", "Default", "Daily coding, balanced speed/quality", "$$"),
        ("claude-sonnet-4-5", "Fast", "Quick edits, iterations, moderate tasks", "$$"),
        ("claude-haiku-4-5", "Fastest", "Simple queries, autocomplete, tests", "$"),
    ]

    for name, tier, desc, cost in models:
        is_current = name == config.model
        style = "bold green" if is_current else ""
        marker = " *" if is_current else ""
        table.add_row(f"{name}{marker}", tier, desc, cost)

    panel = Panel(
        table,
        title="[bold #e5484d]Model Advisor[/bold #e5484d]",
        subtitle="[dim]* = current model · Use /model <name> to switch[/dim]",
        border_style="#e5484d",
        expand=False,
    )
    console.print(panel)

    console.print("\n[bold]Recommended effort levels:[/bold]")
    console.print("  [dim]low[/dim]      Simple fixes, quick questions")
    console.print("  [dim]medium[/dim]   Standard coding tasks")
    console.print("  [dim]high[/dim]     Complex features, refactors (default)")
    console.print("  [dim]xhigh[/dim]    System design, deep analysis, hardest bugs")
    console.print("  [dim]Use --effort <level> or FRENCH_EFFORT env var[/dim]")


def _effort(config: RuntimeConfig, args: list[str] | None = None) -> None:
    import os
    current = os.environ.get("FRENCH_EFFORT") or os.environ.get("CLAUDE_EFFORT") or "high"
    if not args:
        click.echo(f"Current effort level: {current}")
        click.echo("Available: low, medium, high, xhigh")
        click.echo("Usage: /effort <level> or --effort <level>")
        return
    level = args[0].lower()
    if level not in ("low", "medium", "high", "xhigh"):
        raise click.ClickException(f"Invalid effort level: {level}. Use: low, medium, high, xhigh")
    os.environ["FRENCH_EFFORT"] = level
    click.echo(f"Effort level set to: {level}")


def _doctor_enhanced(config: RuntimeConfig) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    import os
    console = Console()

    # Initialize MCP servers to detect failures
    from claude_code_py.services.mcp.client import initialize_mcp_servers, mcp_manager
    try:
        initialize_mcp_servers(config.home, config.cwd)
    except Exception:
        pass

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(width=22, style="dim")
    table.add_column()

    table.add_row("Working directory", str(config.cwd))
    table.add_row("Config home", str(config.home))
    table.add_row("Model", f"[bold #e5484d]{config.model}[/bold #e5484d]")
    table.add_row("Remote", str(config.is_remote))

    from claude_code_py.services.auth import check_auth_status
    auth = check_auth_status(config.home)
    if auth["status"] == "authenticated":
        table.add_row("Authentication", f"[green]Authenticated[/green] ({auth['source']})")
    else:
        table.add_row("Authentication", "[red]Not authenticated[/red]")

    safe_mode = (os.environ.get("FRENCH_SAFE_MODE") or os.environ.get("CLAUDE_CODE_SAFE_MODE")) == "1"
    effort = os.environ.get("FRENCH_EFFORT") or os.environ.get("CLAUDE_EFFORT") or "high"
    table.add_row("Safe mode", "[yellow]ON[/yellow]" if safe_mode else "OFF")
    table.add_row("Effort level", effort)

    # MCP status
    connected = len(mcp_manager.clients)
    failed = len(mcp_manager.failures)
    if connected > 0 or failed > 0:
        mcp_parts = []
        if connected > 0:
            mcp_parts.append(f"[green]{connected} connected[/green]")
        if failed > 0:
            mcp_parts.append(f"[red]{failed} failed[/red]")
        table.add_row("MCP servers", "  ".join(mcp_parts))
    else:
        table.add_row("MCP servers", "[dim]none configured[/dim]")

    if mcp_manager.failures:
        table.add_row("", "")
        for name, failure in mcp_manager.failures.items():
            # Shorten long error messages
            short_err = failure if len(failure) < 60 else failure[:57] + "..."
            table.add_row(f"  [red]{name}[/red]", f"[dim]{short_err}[/dim]")

    # Check Python version
    import sys
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    table.add_row("Python", py_ver)

    # Check dependencies
    deps_ok = True
    for pkg in ["anthropic", "click", "rich", "httpx"]:
        try:
            __import__(pkg)
            table.add_row(f"  {pkg}", "[green]OK[/green]")
        except ImportError:
            table.add_row(f"  {pkg}", "[red]MISSING[/red]")
            deps_ok = False

    has_issues = not deps_ok or mcp_manager.failures
    status = "[yellow]Issues found[/yellow]" if has_issues else "[green]All checks passed[/green]"
    panel = Panel(table, title=f"[bold #e5484d]Doctor[/bold #e5484d] — {status}", border_style="#e5484d", box=box.ROUNDED, expand=False)
    console.print(panel)

command_registry.register("advisor", _advisor, "Show model recommendations for your task type")
command_registry.register("effort", _effort, "Show or set thinking effort level")
# Re-register doctor with enhanced version
command_registry.handlers["doctor"] = _doctor_enhanced
command_registry.commands["doctor"] = Command(name="doctor", description="Diagnose and verify installation and settings", handler=_doctor_enhanced)


# ── New Feature Commands ─────────────────────────────────────────────────────

def _plugins(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Plugin management: list, browse, install, enable, disable, remove."""
    from claude_code_py.components.plugin_system import (
        plugins_list_command, plugins_browse_command, plugins_manage_command,
    )
    args = args or []
    action = args[0] if args else "list"

    if action == "list":
        plugins_list_command(config.home, config.cwd)
    elif action == "browse":
        plugins_browse_command(config.home)
    elif action in ("enable", "disable", "remove"):
        name = args[1] if len(args) > 1 else None
        plugins_manage_command(config.home, config.cwd, action, name)
    elif action == "install":
        plugins_browse_command(config.home)
    else:
        plugins_list_command(config.home, config.cwd)


def _skills(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Skills management: list, view, create, edit, delete, export, import."""
    from claude_code_py.components.skills_manager import (
        skills_list_command, skills_view_command, skills_create_command,
        skills_edit_command, skills_delete_command, skills_export_command,
        skills_import_command,
    )
    args = args or []
    action = args[0] if args else "list"

    if action == "list":
        skills_list_command(config.home, config.cwd)
    elif action == "view":
        name = args[1] if len(args) > 1 else None
        skills_view_command(config.home, config.cwd, name)
    elif action == "create":
        skills_create_command(config.home, config.cwd)
    elif action == "edit":
        name = args[1] if len(args) > 1 else None
        skills_edit_command(config.home, config.cwd, name)
    elif action == "delete":
        name = args[1] if len(args) > 1 else None
        skills_delete_command(config.home, config.cwd, name)
    elif action == "export":
        name = args[1] if len(args) > 1 else None
        skills_export_command(config.home, config.cwd, name)
    elif action == "import":
        skills_import_command(config.home, config.cwd)
    else:
        skills_list_command(config.home, config.cwd)


def _sandbox(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Sandbox mode: run commands in Docker or check environment."""
    from claude_code_py.components.sandbox import get_sandbox_manager
    args = args or []
    action = args[0] if args else "check"

    manager = get_sandbox_manager()
    if action == "check":
        checks = manager.check_environment()
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        all_ok = all(c["status"] == "ok" for c in checks)
        console.print(Panel(
            "\n".join(
                f"  [{'green' if c['status'] == 'ok' else 'red'}]"
                f"{'✔' if c['status'] == 'ok' else '✘'}[/] {c['check']}"
                f"  [dim]{c['detail']}[/]"
                for c in checks
            ),
            title="[bold #e5484d]Sandbox Check[/bold #e5484d]",
            border_style="#e5484d",
            expand=False,
        ))
    elif action == "run" and len(args) > 1:
        command = " ".join(args[1:])
        from rich.console import Console
        from claude_code_py.components.dialog import notification_dialog
        console = Console()
        if not manager.is_available():
            notification_dialog("Sandbox Unavailable", "Docker is required for sandbox mode.", "error")
            return
        console.print(f"  [dim]Running in sandbox ({manager.config.image})...[/]")
        result = manager.run(command, cwd=config.cwd)
        if result.stdout:
            for line in result.stdout.splitlines()[:30]:
                console.print(f"    {line}")
        if result.error:
            console.print(f"  [red]✘ Error: {result.error}[/]")
        else:
            color = "green" if result.exit_code == 0 else "yellow"
            console.print(f"  [{color}]✔[/] Exit code: {result.exit_code}  [dim]{result.duration:.1f}s[/]")
    else:
        from rich.console import Console
        console = Console()
        console.print(f"  [dim]Usage: /sandbox check | run <command>[/]")


def _update(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Check for updates or perform an upgrade."""
    from claude_code_py.components.auto_updater import check_for_updates, perform_update
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    args = args or []
    action = args[0] if args else "check"

    if action == "check":
        result = check_for_updates()
        if result:
            console.print(Panel(
                f"Version [green]{result['version']}[/] is available!\n"
                f"You have [dim]{result['current']}[/]\n\n"
                f"[bold #e5484d]pip install --upgrade frenchie[/]",
                title="[bold #e5484d]Update Available[/bold #e5484d]",
                border_style="green",
                expand=False,
            ))
        else:
            console.print(f"  [dim]You're up to date![/]")
    elif action == "install":
        perform_update()
    else:
        result = check_for_updates()
        if result:
            console.print(f"  [green]✔[/] Version {result['version']} available. Run /update install")
        else:
            console.print(f"  [dim]✔[/] Up to date")


def _voice(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Voice input: record from microphone and transcribe."""
    from claude_code_py.components.voice_mode import is_voice_available, transcribe_microphone
    from rich.console import Console
    console = Console()
    args = args or []

    if not is_voice_available():
        console.print(f"  [yellow]⚠[/] Voice input requires 'SpeechRecognition' package")
        console.print(f"  [dim]pip install SpeechRecognition[/]")
        return

    console.print(f"  [dim]🎤 Listening for 5 seconds...[/]")
    text = transcribe_microphone()
    if text:
        console.print(f"  [green]✔[/] Recognized: [bold]{text}[/]")
        # If there's an active conversation, submit the transcribed text
        # For now, just print it
    else:
        console.print(f"  [yellow]⚠[/] No speech detected or transcription failed")


command_registry.register("plugins", _plugins, "Manage plugins: list, browse, install, enable, disable, remove")
command_registry.register("skills", _skills, "Manage skills: list, view, create, edit, delete, export, import")
command_registry.register("sandbox", _sandbox, "Sandbox mode: check Docker setup, run commands isolated")
command_registry.register("update", _update, "Check for updates or upgrade Frenchie")

def _logs(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Show recent log entries or log file path.

    Usage: /logs [tail n] [path]
    - Without args: show last 50 lines
    - /logs tail 100: show last 100 lines
    - /logs path: show log file path
    """
    from claude_code_py.logger import show_log_tail, log_path_command
    args = args or []
    if args and args[0] == "path":
        log_path_command(config.home)
    elif args and args[0] == "tail" and len(args) > 1:
        try:
            n = int(args[1])
            show_log_tail(config.home, n=n)
        except ValueError:
            show_log_tail(config.home, n=50)
    else:
        show_log_tail(config.home, n=50)


def _mode(config: RuntimeConfig, args: list[str] | None = None) -> None:
    """Switch or show the active execution mode.

    Usage: /mode [plan | build | auto]
    """
    from claude_code_py.services.state_store import StateStore
    from rich.console import Console
    console = Console()
    args = args or []
    store = StateStore()

    # Check if a specific mode is passed
    if args:
        target = args[0].lower()
        if target == "plan":
            store.set("permission_mode", "plan")
            console.print(f"  [bold #ff8787]▸[/] Mode switched to [bold #ff8787]plan[/] (read-only, research & outline steps first).")
        elif target in ("build", "default"):
            store.set("permission_mode", "default")
            console.print(f"  [bold #ff8787]▸[/] Mode switched to [bold #ff8787]build[/] (interactive, allows edits and terminal commands).")
        elif target == "auto":
            store.set("permission_mode", "auto")
            console.print(f"  [bold #ff8787]▸[/] Mode switched to [bold #ff8787]auto[/] (fully automated, allows edits and terminal commands without prompt).")
        else:
            console.print(f"  [bold red]✘[/] Unknown mode: {target}. Available modes: plan, build, auto.")
        return

    # If no args, display the current mode and let the user select interactively
    current = store.load().get("permission_mode", "default")
    if current == "default":
        current_display = "build"
    else:
        current_display = current

    choices = [
        ("plan", "Plan mode (read-only, research & design)"),
        ("build", "Build mode (default interactive, prompts for writes/executes)"),
        ("auto", "Auto mode (fully automated, bypasses permission prompts)"),
    ]

    from claude_code_py.tui import _arrow_select
    try:
        console.print(f"  [bold #ff8787]▸[/] Current mode: [bold #ff8787]{current_display}[/]")
        console.print(f"  [dim]Select a mode to switch to:[/dim]")
        idx = _arrow_select(choices, title="")
    except (KeyboardInterrupt, EOFError):
        idx = None

    if idx is None:
        console.print(f"  [dim]Cancelled.[/dim]")
        return

    selected_mode = choices[idx][0]
    if selected_mode == "build":
        store.set("permission_mode", "default")
    else:
        store.set("permission_mode", selected_mode)

    console.print(f"  [bold green]✔[/] Switched to [bold]{selected_mode}[/] mode.")


command_registry.register("mode", _mode, "Switch or show execution mode (plan, build, auto)")
command_registry.register("logs", _logs, "Show recent log entries", aliases=("log",))
command_registry.register("voice", _voice, "Voice input: transcribe from microphone")
