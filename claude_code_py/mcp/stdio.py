from __future__ import annotations

import json
import sys
from typing import Any

from .explorer import ClaudeCodeExplorer


def handle_request(explorer: ClaudeCodeExplorer, request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    request_id = request.get("id")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "frenchie-explorer", "version": "1.1.0-python"},
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            }
        elif method == "tools/list":
            result = {"tools": explorer.list_mcp_tools()}
        elif method == "tools/call":
            params = request.get("params", {})
            result = explorer.call_tool(params.get("name"), params.get("arguments", {}))
        elif method == "resources/list":
            result = {
                "resources": [
                    {"uri": "frenchie://architecture", "name": "Architecture Overview", "mimeType": "text/markdown"},
                    {"uri": "frenchie://tools", "name": "Tool Registry", "mimeType": "application/json"},
                    {"uri": "frenchie://commands", "name": "Command Registry", "mimeType": "application/json"},
                ]
            }
        else:
            raise ValueError(f"Unsupported method: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve_stdio() -> None:
    explorer = ClaudeCodeExplorer.from_environment()
    explorer.validate_src_root()
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_request(explorer, json.loads(line))
        print(json.dumps(response, ensure_ascii=False), flush=True)
