"""MCP server disabled-state persistence.

Previously this lived inside ``~/.claude.json`` (the original Claude Code
config).  It now lives in ``<home>/.frenchie/mcp_disabled/`` so that
Frenchie never touches the Claude Code config tree.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claude_code_py.services.config_store import config_dir


def _disabled_state_path(cwd: Path, home: Path | None = None) -> Path:
    """Return the path to the per-project disabled-state file.

    For simplicity each project gets its own file keyed by the normalised cwd
    so we don't have to maintain a single shared JSON with project sub-keys.
    """
    project_key = str(cwd.resolve()).replace(":", "").replace("\\", "-").replace("/", "-").strip("-")
    return config_dir(home) / "mcp_disabled" / f"{project_key}.json"


def _read_disabled(cwd: Path, home: Path | None = None) -> dict[str, Any]:
    path = _disabled_state_path(cwd, home)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_disabled(cwd: Path, data: dict[str, Any], home: Path | None = None) -> None:
    path = _disabled_state_path(cwd, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_mcp_server_disabled(name: str, cwd: Path, home: Path | None = None) -> bool:
    data = _read_disabled(cwd, home)
    disabled_list: list[str] = data.get("disabledMcpServers", [])
    return name in disabled_list


def set_mcp_server_disabled_state(name: str, disabled: bool, cwd: Path, home: Path | None = None) -> None:
    data = _read_disabled(cwd, home)
    disabled_list: list[str] = data.setdefault("disabledMcpServers", [])

    if disabled:
        if name not in disabled_list:
            disabled_list.append(name)
    else:
        if name in disabled_list:
            disabled_list.remove(name)

    _write_disabled(cwd, data, home)
