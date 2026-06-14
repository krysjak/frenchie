from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from claude_code_py.services.config_store import config_dir, load_config


def mcp_config_path(home: Path) -> Path:
    """Path to the Frenchie-owned MCP config file inside .frenchie/."""
    return config_dir(home) / "mcp.json"


def load_mcp_config(home: Path, cwd: Path) -> dict[str, dict[str, Any]]:
    # 1. Load user MCP servers from .frenchie/mcp.json
    global_mcp: dict[str, dict[str, Any]] = {}
    mcp_path = mcp_config_path(home)
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8-sig"))
            global_mcp = data.get("mcpServers", {})
            if not isinstance(global_mcp, dict):
                global_mcp = {}
        except Exception:
            pass

    # Fallback: also check the main config file (frenchie.json)
    if not global_mcp:
        main_config = load_config(home)
        global_mcp = main_config.get("mcpServers", {})
        if not isinstance(global_mcp, dict):
            global_mcp = {}

    # 2. Load workspace settings (.mcp.json)
    workspace_mcp: dict[str, dict[str, Any]] = {}
    workspace_path = cwd / ".mcp.json"
    if workspace_path.exists():
        try:
            data = json.loads(workspace_path.read_text(encoding="utf-8-sig"))
            workspace_mcp = data.get("mcpServers", {})
            if not isinstance(workspace_mcp, dict):
                workspace_mcp = {}
        except Exception:
            pass

    # Merge configs (workspace config overrides global config)
    merged: dict[str, dict[str, Any]] = {}
    for name, cfg in global_mcp.items():
        if isinstance(cfg, dict):
            merged[name] = cfg
    for name, cfg in workspace_mcp.items():
        if isinstance(cfg, dict):
            merged[name] = cfg

    return merged


def add_mcp_server(name: str, server_config: dict[str, Any], home: Path) -> None:
    """Add an MCP server to .frenchie/mcp.json (user scope)."""
    path = mcp_config_path(home)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            data = {}
    else:
        data = {}
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
    servers[name] = server_config
    data["mcpServers"] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def remove_mcp_server(name: str, home: Path) -> bool:
    """Remove an MCP server from .frenchie/mcp.json. Returns True if removed."""
    path = mcp_config_path(home)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    servers = data.get("mcpServers", {})
    if name not in servers:
        return False
    del servers[name]
    data["mcpServers"] = servers
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True
