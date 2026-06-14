from __future__ import annotations

from typing import Any
from claude_code_py.mcp.explorer import ClaudeCodeExplorer


def list_mcp_resources(server: str | None = None) -> list[dict[str, Any]]:
    from claude_code_py.services.mcp.client import mcp_manager

    resources = [
        {
            "uri": "frenchie://architecture",
            "name": "Architecture Overview",
            "mimeType": "text/markdown",
            "description": "High-level overview of the Frenchie source architecture",
            "server": "frenchie-explorer",
        },
        {
            "uri": "frenchie://tools",
            "name": "Tool Registry",
            "mimeType": "application/json",
            "description": "List of all agent tools with their files",
            "server": "frenchie-explorer",
        },
        {
            "uri": "frenchie://commands",
            "name": "Command Registry",
            "mimeType": "application/json",
            "description": "List of all slash commands",
            "server": "frenchie-explorer",
        },
    ]

    for client_name, client in mcp_manager.clients.items():
        try:
            client_resources = client.list_resources()
            for res in client_resources:
                res_copy = dict(res)
                res_copy["server"] = client_name
                resources.append(res_copy)
        except Exception:
            pass

    if server:
        return [resource for resource in resources if resource.get("server") == server]
    return resources


def read_mcp_resource(server: str, uri: str) -> dict[str, object]:
    from claude_code_py.services.mcp.client import mcp_manager

    if server == "claude-code-explorer":
        explorer = ClaudeCodeExplorer.from_environment()
        if uri == "claude-code://architecture":
            text = explorer.get_architecture()
            mime_type = "text/markdown"
        elif uri == "claude-code://tools":
            text = explorer.call_tool("list_tools")["content"][0]["text"]
            mime_type = "application/json"
        elif uri == "claude-code://commands":
            text = explorer.call_tool("list_commands")["content"][0]["text"]
            mime_type = "application/json"
        elif uri.startswith("claude-code://source/"):
            text = explorer.read_source_file(uri.removeprefix("claude-code://source/"))
            mime_type = "text/plain"
        else:
            raise ValueError(f"Unknown resource: {uri}")
        return {"contents": [{"uri": uri, "mimeType": mime_type, "text": text}]}

    client = mcp_manager.get_client(server)
    if not client:
        raise ValueError(f'Server "{server}" not found.')

    try:
        return client.read_resource(uri)
    except Exception as exc:
        raise ValueError(f"Failed to read resource '{uri}' from server '{server}': {exc}") from exc
