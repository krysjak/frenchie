from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_code_py.services.mcp.client import McpProcessClient, mcp_manager, initialize_mcp_servers
from claude_code_py.tools.registry import tool_registry

# Mock MCP Server source code
MOCK_SERVER_CODE = """
import sys
import json

def main():
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        try:
            line_bytes = stdin.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8").strip()
            if not line.startswith("Content-Length:"):
                continue
            length = int(line.split(":")[1].strip())
            stdin.readline() # blank line
            body_bytes = stdin.read(length)
            try:
                req = json.loads(body_bytes.decode("utf-8"))
            except Exception as e:
                sys.stderr.write(f"JSON Parse Error: {e}\\n")
                sys.stderr.write(f"body_bytes length: {len(body_bytes)}\\n")
                sys.stderr.write(f"body_bytes content: {repr(body_bytes)}\\n")
                sys.stderr.flush()
                raise
            
            req_id = req.get("id")
            method = req.get("method")
            
            resp_result = {}
            if method == "initialize":
                resp_result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"}
                }
            elif method == "tools/list":
                resp_result = {
                    "tools": [
                        {
                            "name": "echo_tool",
                            "description": "Echos back arguments",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"}
                                }
                            }
                        }
                    ]
                }
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                if name == "echo_tool":
                    msg = arguments.get("message", "empty")
                    resp_result = {
                        "content": [{"type": "text", "text": f"Echo: {msg}"}]
                    }
                else:
                    resp_result = {"content": []}
            elif method == "resources/list":
                resp_result = {
                    "resources": [
                        {
                            "uri": "mock://test-resource",
                            "name": "Mock Resource",
                            "mimeType": "text/plain",
                            "description": "A test mock resource"
                        }
                    ]
                }
            elif method == "resources/read":
                params = req.get("params", {})
                uri = params.get("uri")
                if uri == "mock://test-resource":
                    resp_result = {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "text/plain",
                                "text": "Hello from mock resource!"
                            }
                        ]
                    }
                else:
                    resp_result = {"contents": []}
            
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": resp_result
                }
                resp_str = json.dumps(resp, ensure_ascii=False)
                resp_bytes = resp_str.encode("utf-8")
                header = f"Content-Length: {len(resp_bytes)}\\r\\n\\r\\n".encode("utf-8")
                stdout.write(header + resp_bytes)
                stdout.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\\n")
            sys.stderr.flush()
            break

if __name__ == "__main__":
    main()
"""

def test_client_and_methods(server_path: Path):
    # Setup client
    client = McpProcessClient("test-mock", sys.executable, [str(server_path)])
    try:
        client.connect()
        init_res = client.initialize()
        assert init_res.get("serverInfo", {}).get("name") == "mock-mcp-server"

        # List tools
        tools = client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "echo_tool"

        # Call tool
        call_res = client.call_tool("echo_tool", {"message": "hello unit test"})
        assert call_res.get("content", [])[0]["text"] == "Echo: hello unit test"

        # List resources
        resources = client.list_resources()
        assert len(resources) == 1
        assert resources[0]["uri"] == "mock://test-resource"

        # Read resource
        resource_data = client.read_resource("mock://test-resource")
        assert resource_data.get("contents", [])[0]["text"] == "Hello from mock resource!"

    finally:
        client.close()


def test_manager_and_dynamic_registration(server_path: Path, temp_dir: Path):
    home_dir = temp_dir / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    cwd_dir = temp_dir / "cwd"
    cwd_dir.mkdir(parents=True, exist_ok=True)

    # Write settings.json (global settings) with no servers
    global_settings = {"mcpServers": {}}
    (home_dir / ".claude").mkdir(parents=True, exist_ok=True)
    with open(home_dir / ".claude" / "settings.json", "w", encoding="utf-8") as f:
        json.dump(global_settings, f)

    # Write .mcp.json in project cwd directory
    workspace_settings = {
        "mcpServers": {
            "mock-workspace-server": {
                "command": sys.executable,
                "args": [str(server_path)]
            }
        }
    }
    with open(cwd_dir / ".mcp.json", "w", encoding="utf-8") as f:
        json.dump(workspace_settings, f)

    # Clear mcp_manager clients to start clean
    mcp_manager.close_all()

    # Before initializing, check tool registry doesn't have "echo_tool"
    if "echo_tool" in tool_registry.tools:
        del tool_registry.tools["echo_tool"]

    # Run initialization
    initialize_mcp_servers(home_dir, cwd_dir)

    # Verify workspace server connected and registered
    assert "mock-workspace-server" in mcp_manager.clients
    assert "echo_tool" in tool_registry.tools

    # Test invoking registered tool via tool_registry
    tool = tool_registry.get("echo_tool")
    res = tool.call(message="via registry")
    assert res[0]["text"] == "Echo: via registry"

    # Clean up mcp_manager
    mcp_manager.close_all()


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        server_path = tmp_path / "mock_server.py"
        with open(server_path, "w", encoding="utf-8") as f:
            f.write(MOCK_SERVER_CODE)
        
        print("Running MCP client method assertions...")
        test_client_and_methods(server_path)
        print("MCP client methods OK")
        
        print("Running MCP manager & registration assertions...")
        test_manager_and_dynamic_registration(server_path, tmp_path)
        print("MCP manager & registration OK")
        
        print("All MCP client unit tests OK")


if __name__ == "__main__":
    main()
