"""Plugin System — Plugin registry, marketplace discovery, and management.

Inspired by the official Claude Code plugin system with marketplace support.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen
from urllib.error import URLError

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from claude_code_py.components.fuzzy_picker import fuzzy_picker, FuzzyItem
from claude_code_py.components.dialog import confirm_dialog, notification_dialog, input_dialog


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


@dataclass
class PluginManifest:
    """Plugin manifest matching the official Claude Code plugin format."""
    name: str
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    license: str = ""
    entry: str = "plugin.py"
    tools: list[dict[str, Any]] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.0.1"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            homepage=data.get("homepage", ""),
            license=data.get("license", ""),
            entry=data.get("entry", "plugin.py"),
            tools=data.get("tools", []),
            commands=data.get("commands", []),
            requires=data.get("requires", []),
            config_schema=data.get("config_schema", {}),
        )


@dataclass
class Plugin:
    """A loaded plugin instance."""
    manifest: PluginManifest
    path: Path
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """Registry for discovering, loading, and managing plugins."""

    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self._marketplace_cache: list[PluginManifest] | None = None

    def discover_plugins(self, home: Path, cwd: Path) -> list[Plugin]:
        """Discover plugins from all plugin directories."""
        from claude_code_py.services.config_store import project_dir
        plugin_dirs = [
            project_dir(cwd) / "plugins",
            home / ".frenchie" / "plugins",
            home / ".claude" / "plugins",
            home / ".codebuff" / "plugins",
        ]

        discovered = []
        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                continue
            for manifest_file in plugin_dir.glob("**/plugin.json"):
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
                    manifest = PluginManifest.from_dict(data)
                    plugin = Plugin(
                        manifest=manifest,
                        path=manifest_file.parent,
                    )
                    # Check disabled list
                    disabled_path = plugin_dir / ".disabled"
                    if disabled_path.exists():
                        disabled = set(
                            line.strip()
                            for line in disabled_path.read_text().splitlines()
                            if line.strip()
                        )
                        plugin.enabled = manifest.name not in disabled
                    discovered.append(plugin)
                except Exception as e:
                    from rich.markup import escape as _esc
                    console.print(f"  [{ACCENT_YELLOW}]⚠[/] Failed to load plugin from {manifest_file}: {_esc(str(e))}")

        # Register discovered plugins
        for plugin in discovered:
            self.plugins[plugin.manifest.name] = plugin

        return discovered

    def get_plugin(self, name: str) -> Plugin | None:
        return self.plugins.get(name)

    def list_plugins(self) -> list[Plugin]:
        return list(self.plugins.values())

    def enable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if not plugin:
            return False
        plugin.enabled = True
        return True

    def disable_plugin(self, name: str) -> bool:
        plugin = self.plugins.get(name)
        if not plugin:
            return False
        plugin.enabled = False
        return True

    def remove_plugin(self, name: str) -> bool:
        return self.plugins.pop(name, None) is not None

    def get_marketplace_listings(self, force_refresh: bool = False) -> list[PluginManifest]:
        """Fetch plugin marketplace listings from a remote registry.

        Falls back to a curated built-in list if the network is unavailable.
        """
        if self._marketplace_cache and not force_refresh:
            return self._marketplace_cache

        # Try to fetch from marketplaces
        marketplaces = [
            "https://raw.githubusercontent.com/anthropics/claude-code-plugins/main/registry.json",
        ]

        for marketplace_url in marketplaces:
            try:
                resp = urlopen(marketplace_url, timeout=5)
                data = json.loads(resp.read().decode("utf-8"))
                listings = [PluginManifest.from_dict(item) for item in data.get("plugins", [])]
                self._marketplace_cache = listings
                return listings
            except (URLError, json.JSONDecodeError, Exception):
                continue

        # Fallback: built-in curated list
        self._marketplace_cache = self._builtin_listings()
        return self._marketplace_cache

    def _builtin_listings(self) -> list[PluginManifest]:
        """Built-in curated plugin listings when network is unavailable."""
        return [
            PluginManifest(
                name="git-integration",
                version="1.0.0",
                description="Advanced git integration: blame, log, rebase helpers",
                author="Frenchie",
            ),
            PluginManifest(
                name="docker-tools",
                version="1.0.0",
                description="Docker container management and inspection tools",
                author="Frenchie",
            ),
            PluginManifest(
                name="jupyter-helper",
                version="1.0.0",
                description="Enhanced Jupyter notebook operations",
                author="Frenchie",
            ),
            PluginManifest(
                name="code-formatter",
                version="1.0.0",
                description="Auto-format code with black, ruff, prettier",
                author="Frenchie",
            ),
            PluginManifest(
                name="test-runner",
                version="1.0.0",
                description="Run tests and analyze coverage reports",
                author="Frenchie",
            ),
            PluginManifest(
                name="api-tester",
                version="1.0.0",
                description="HTTP API testing from the terminal",
                author="Frenchie",
            ),
        ]

    def install_from_marketplace(
        self,
        manifest: PluginManifest,
        home: Path,
    ) -> bool:
        """Install a plugin from the marketplace.

        This creates a plugin stub directory.
        """
        plugin_dir = home / ".frenchie" / "plugins" / manifest.name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        manifest_path = plugin_dir / "plugin.json"
        manifest_data = {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "homepage": manifest.homepage,
            "license": manifest.license,
            "entry": manifest.entry,
            "tools": manifest.tools,
            "commands": manifest.commands,
            "requires": manifest.requires,
        }
        manifest_path.write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Create stub entry
        entry_path = plugin_dir / (manifest.entry or "plugin.py")
        if not entry_path.exists():
            entry_path.write_text(
                f'"""Plugin: {manifest.name}\n\n{manifest.description}\n"""\n\n'
                f'def register() -> dict:\n'
                f'    """Register plugin hooks and return metadata."""\n'
                f'    return {{\n'
                f'        "name": "{manifest.name}",\n'
                f'        "version": "{manifest.version}",\n'
                f'        "tools": [],\n'
                f'        "commands": [],\n'
                f'    }}\n',
                encoding="utf-8",
            )

        # Register
        plugin = Plugin(manifest=manifest, path=plugin_dir)
        self.plugins[manifest.name] = plugin
        return True


# Global registry singleton
_plugin_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry()
    return _plugin_registry


# ── Command Handlers ─────────────────────────────────────────────────────────

def plugins_list_command(home: Path, cwd: Path) -> None:
    """List all installed plugins."""
    registry = get_plugin_registry()
    registry.discover_plugins(home, cwd)
    plugins = registry.list_plugins()

    if not plugins:
        console.print(Panel(
            Text("No plugins installed.", style=TEXT_DIM),
            title=f"[bold {CLAUDE_ORANGE}]Plugins[/bold {CLAUDE_ORANGE}]",
            border_style=CLAUDE_ORANGE,
            box=box.ROUNDED,
            expand=False,
        ))
        return

    table = Table(
        show_header=True,
        header_style=f"bold {CLAUDE_ORANGE}",
        padding=(0, 2),
        box=None,
    )
    table.add_column("Plugin", style="bold")
    table.add_column("Version", width=10)
    table.add_column("Status", width=10)
    table.add_column("Description")

    for plugin in plugins:
        status = f"[{ACCENT_GREEN}]enabled[/]" if plugin.enabled else f"[{TEXT_DIM}]disabled[/]"
        table.add_row(
            plugin.manifest.name,
            plugin.manifest.version,
            status,
            plugin.manifest.description,
        )

    console.print(Panel(
        table,
        title=f"[bold {CLAUDE_ORANGE}]Installed Plugins ({len(plugins)})[/bold {CLAUDE_ORANGE}]",
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
    ))


def plugins_browse_command(home: Path) -> None:
    """Browse and install plugins from the marketplace."""
    registry = get_plugin_registry()
    notification_dialog("Marketplace", "Fetching available plugins...", "info")

    listings = registry.get_marketplace_listings()
    if not listings:
        console.print(f"  [{ACCENT_YELLOW}]⚠[/] No plugins available.")
        return

    # Show marketplace
    table = Table(
        show_header=True,
        header_style=f"bold {CLAUDE_ORANGE}",
        padding=(0, 2),
        box=None,
    )
    table.add_column("#", width=3)
    table.add_column("Plugin")
    table.add_column("Version", width=10)
    table.add_column("Author", width=16)
    table.add_column("Description")

    for i, listing in enumerate(listings, 1):
        table.add_row(
            str(i),
            listing.name,
            listing.version,
            listing.author,
            listing.description,
        )

    console.print(Panel(
        table,
        title=f"[bold {CLAUDE_ORANGE}]Plugin Marketplace ({len(listings)})[/bold {CLAUDE_ORANGE}]",
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
    ))

    # Ask which to install
    try:
        choice = console.input(
            f"  [{CLAUDE_ORANGE}]▸[/] Enter number to install (or empty to cancel): "
        ).strip()
        if not choice:
            return
        idx = int(choice) - 1
        if 0 <= idx < len(listings):
            manifest = listings[idx]
            if confirm_dialog("Install Plugin", f"Install '{manifest.name}' v{manifest.version}?"):
                if registry.install_from_marketplace(manifest, home):
                    notification_dialog("Installed", f"Plugin '{manifest.name}' installed.", "success")
                else:
                    notification_dialog("Error", f"Failed to install '{manifest.name}'.", "error")
        else:
            console.print(f"  [{ACCENT_RED}]✘[/] Invalid choice.")
    except (ValueError, EOFError, KeyboardInterrupt):
        pass


def plugins_manage_command(home: Path, cwd: Path, action: str, name: str | None = None) -> None:
    """Manage plugins: enable, disable, remove."""
    registry = get_plugin_registry()
    registry.discover_plugins(home, cwd)

    if action == "enable":
        if not name:
            # Show picker
            plugins = registry.list_plugins()
            disabled = [p for p in plugins if not p.enabled]
            if not disabled:
                console.print(f"  [{TEXT_DIM}]No disabled plugins.[/]")
                return
            choices = [(p.manifest.name, p.manifest.description) for p in disabled]
            selected = fuzzy_picker(choices, "Select plugin to enable")
            if selected:
                name = selected
        if name and registry.enable_plugin(name):
            notification_dialog("Enabled", f"Plugin '{name}' enabled.", "success")
        else:
            console.print(f"  [{ACCENT_RED}]✘[/] Plugin '{name}' not found.")

    elif action == "disable":
        if not name:
            plugins = registry.list_plugins()
            enabled = [p for p in plugins if p.enabled]
            if not enabled:
                console.print(f"  [{TEXT_DIM}]No enabled plugins.[/]")
                return
            choices = [(p.manifest.name, p.manifest.description) for p in enabled]
            selected = fuzzy_picker(choices, "Select plugin to disable")
            if selected:
                name = selected
        if name and registry.disable_plugin(name):
            notification_dialog("Disabled", f"Plugin '{name}' disabled.", "success")
        else:
            console.print(f"  [{ACCENT_RED}]✘[/] Plugin '{name}' not found.")

    elif action == "remove":
        if not name:
            plugins = registry.list_plugins()
            if not plugins:
                console.print(f"  [{TEXT_DIM}]No plugins installed.[/]")
                return
            choices = [(p.manifest.name, p.manifest.description) for p in plugins]
            selected = fuzzy_picker(choices, "Select plugin to remove")
            if selected:
                name = selected
        if name:
            if confirm_dialog("Remove Plugin", f"Remove '{name}'?", warn=True):
                registry.remove_plugin(name)
                notification_dialog("Removed", f"Plugin '{name}' removed.", "info")
