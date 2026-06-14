"""Auto-updater — Check for updates and self-update.

Inspired by the official Claude Code auto-updater components
(NativeAutoUpdater, PackageManagerAutoUpdater).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from claude_code_py import __version__
from claude_code_py.components.dialog import confirm_dialog, notification_dialog


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


def check_for_updates(
    current_version: str = __version__,
    pypi_package: str = "frenchie",
) -> dict[str, Any] | None:
    """Check PyPI for a newer version.

    Returns dict with 'version', 'url' if newer version exists, else None.
    """
    pypi_name = pypi_package

    try:
        req = Request(
            f"https://pypi.org/pypi/{pypi_name}/json",
            headers={"Accept": "application/json"},
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest = data.get("info", {}).get("version", "")
        if not latest:
            return None

        # Compare versions
        if _compare_versions(latest, current_version) > 0:
            return {
                "version": latest,
                "current": current_version,
                "url": data.get("info", {}).get("package_url", f"https://pypi.org/project/{pypi_name}/"),
                "release_url": data.get("info", {}).get("release_url", ""),
                "summary": data.get("info", {}).get("summary", ""),
            }
        return None

    except (URLError, json.JSONDecodeError, Exception):
        return None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Returns >0 if v1 > v2."""
    def parse(v: str):
        return [int(x) for x in v.split(".") if x.isdigit()]

    parts1 = parse(v1)
    parts2 = parse(v2)

    for i in range(max(len(parts1), len(parts2))):
        p1 = parts1[i] if i < len(parts1) else 0
        p2 = parts2[i] if i < len(parts2) else 0
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
    return 0


def check_and_notify(
    console_obj: Console | None = None,
    package_name: str = "frenchie",
) -> None:
    """Check for updates and notify the user if available."""
    c = console_obj or console
    result = check_for_updates(pypi_package=package_name)

    if result:
        panel = Panel(
            Text.assemble(
                (f"Version {result['version']} ", ACCENT_GREEN),
                ("is now available! ", TEXT_SECONDARY),
                (f"\nYou have {result['current']}", TEXT_DIM),
                ("\n\n", ""),
                (f"> pip install --upgrade {package_name}", CLAUDE_ORANGE),
            ),
            title=f"[bold {CLAUDE_ORANGE}]Update Available[/bold {CLAUDE_ORANGE}]",
            border_style=ACCENT_GREEN,
            box=box.ROUNDED,
            expand=False,
        )
        c.print(panel)


def perform_update(package_name: str = "frenchie") -> bool:
    """Perform a pip upgrade."""
    if not confirm_dialog("Update", f"Upgrade '{package_name}' to the latest version?"):
        return False

    c = Console()
    c.print(f"  [{CLAUDE_DIM}]Upgrading {package_name}...[/]")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            notification_dialog("Updated", f"Successfully updated to the latest version.", "success")
            return True
        else:
            notification_dialog(
                "Update Failed",
                f"pip install failed:\n{result.stderr[:200]}",
                "error",
            )
            return False
    except subprocess.TimeoutExpired:
        notification_dialog("Update Failed", "Timed out waiting for pip install.", "error")
        return False
    except FileNotFoundError:
        notification_dialog("Update Failed", "pip not found. Use your package manager to update.", "error")
        return False
