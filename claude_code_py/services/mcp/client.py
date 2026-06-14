from __future__ import annotations

import atexit
import json
import os
import subprocess
import queue
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
import httpx


class McpProcessClient:
    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None) -> None:
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process: subprocess.Popen[str] | None = None
        self.request_id = 0

    def connect(self) -> None:
        if self.process is not None:
            return

        # Prepare environment
        process_env = os.environ.copy()
        process_env.update(self.env)

        # Spawn stdio server
        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=process_env,
                bufsize=0,  # Unbuffered for immediate delivery
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to spawn MCP server '{self.name}': {exc}") from exc

    def write_message(self, msg: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Not connected")
        payload = json.dumps(msg, ensure_ascii=False)
        payload_bytes = payload.encode("utf-8")
        header = f"Content-Length: {len(payload_bytes)}\r\n\r\n".encode("utf-8")
        try:
            self.process.stdin.write(header + payload_bytes)
            self.process.stdin.flush()
        except Exception as exc:
            raise RuntimeError(f"Failed to write to MCP server '{self.name}': {exc}") from exc

    def read_message(self) -> dict[str, Any] | None:
        if not self.process or not self.process.stdout:
            raise RuntimeError("Not connected")
        
        # Read header line-by-line
        try:
            line_bytes = self.process.stdout.readline()
            if not line_bytes:
                return None
            line = line_bytes.decode("utf-8").strip()
            if not line.startswith("Content-Length:"):
                return None
            length = int(line.split(":")[1].strip())
            
            # Read the separating blank line
            empty_line = self.process.stdout.readline()
            
            # Read the JSON payload bytes
            payload_bytes = self.process.stdout.read(length)
            return json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Failed to read from MCP server '{self.name}': {exc}") from exc

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.request_id += 1
        req_id = self.request_id
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
            "params": params or {},
        }
        self.write_message(msg)

        # Read JSON-RPC messages until response matches our req_id
        while True:
            resp = self.read_message()
            if resp is None:
                raise RuntimeError(f"Connection lost with MCP server '{self.name}'")
            if resp.get("id") == req_id:
                if "error" in resp:
                    raise RuntimeError(f"MCP server '{self.name}' error: {resp['error']}")
                return resp.get("result", {})

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        self.write_message(msg)

    def initialize(self) -> dict[str, Any]:
        result = self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-code-py", "version": "0.0.1"},
            },
        )
        self.send_notification("notifications/initialized")
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.send_request("tools/call", {"name": name, "arguments": arguments or {}})

    def list_resources(self) -> list[dict[str, Any]]:
        try:
            result = self.send_request("resources/list")
            return result.get("resources", [])
        except Exception:
            return []

    def read_resource(self, uri: str) -> dict[str, Any]:
        return self.send_request("resources/read", {"uri": uri})

    def close(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


class McpHttpClient:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url
        self.post_url: str | None = None
        self.client = httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0))
        self.thread: threading.Thread | None = None
        self.connected = False
        self.request_id = 0
        self.response_queues: dict[int | str, queue.Queue] = {}
        self.lock = threading.Lock()
        self.error: Exception | None = None
        
        # Compatibility fields
        self.command = "http"
        self.args = [url]
        self.process = None

    def connect(self) -> None:
        if self.connected:
            return
            
        self.connected = True
        self.thread = threading.Thread(target=self._read_sse_stream, daemon=True)
        self.thread.start()

        # Wait for post_url to be retrieved from the first SSE event
        import time
        start_time = time.time()
        while self.post_url is None:
            if self.error:
                err = self.error
                self.connected = False
                err_str = str(err)
                # Provide user-friendly error messages
                if isinstance(err, (httpx.ConnectTimeout, TimeoutError)) or "timed out" in err_str.lower() or "10060" in err_str:
                    raise TimeoutError(
                        f"MCP server '{self.name}' timed out connecting to {self.url}. "
                        f"Server may not be running. Disable with: frenchie mcp disable {self.name}"
                    ) from err
                if isinstance(err, (httpx.ConnectError, ConnectionRefusedError, OSError)) or "10061" in err_str or "actively refused" in err_str:
                    raise ConnectionError(
                        f"MCP server '{self.name}' is not running ({self.url}). "
                        f"Start the server or disable it with: frenchie mcp disable {self.name}"
                    ) from err
                raise RuntimeError(f"MCP server '{self.name}' connection failed: {err}") from err
            if not self.thread.is_alive():
                self.close()
                raise RuntimeError(
                    f"MCP server '{self.name}' failed to connect. "
                    f"Check if the server is running at {self.url}"
                )
            if time.time() - start_time > 5.0:
                self.close()
                raise TimeoutError(
                    f"MCP server '{self.name}' timed out (5s) waiting for {self.url}. "
                    f"Start the server or disable it with: frenchie mcp disable {self.name}"
                )
            time.sleep(0.05)

    def _read_sse_stream(self) -> None:
        try:
            with httpx.stream("GET", self.url, timeout=httpx.Timeout(5.0, connect=3.0)) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP GET {self.url} returned status {response.status_code}")
                
                current_event: str | None = None
                data_lines: list[str] = []
                
                for line_bytes in response.iter_lines():
                    if not self.connected:
                        break
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        if data_lines:
                            data_str = "\n".join(data_lines)
                            self._handle_sse_event(current_event, data_str)
                            data_lines = []
                        current_event = None
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[len("data:"):].strip())
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                ConnectionError, ConnectionRefusedError, OSError) as e:
            self.error = e
            self.connected = False
        except Exception as e:
            self.error = e
            self.connected = False

    def _handle_sse_event(self, event: str | None, data: str) -> None:
        if event == "endpoint":
            self.post_url = urljoin(self.url, data)
        elif event == "message" or not event:
            try:
                msg = json.loads(data)
                req_id = msg.get("id")
                if req_id is not None:
                    with self.lock:
                        q = self.response_queues.get(req_id)
                    if q is not None:
                        q.put(msg)
            except Exception:
                pass

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.connected or not self.post_url:
            raise RuntimeError("Not connected")
            
        self.request_id += 1
        req_id = self.request_id
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
            "params": params or {},
        }
        
        resp_queue = queue.Queue()
        with self.lock:
            self.response_queues[req_id] = resp_queue
            
        try:
            resp = self.client.post(self.post_url, json=msg, timeout=30.0)
            if resp.status_code not in (200, 202, 204):
                raise RuntimeError(f"HTTP POST to {self.post_url} returned status {resp.status_code}")
                
            try:
                resp_msg = resp_queue.get(timeout=30.0)
            except queue.Empty:
                raise TimeoutError(f"Timeout waiting for response to request {req_id}")
                
            if "error" in resp_msg:
                raise RuntimeError(f"MCP server '{self.name}' error: {resp_msg['error']}")
            return resp_msg.get("result", {})
        finally:
            with self.lock:
                self.response_queues.pop(req_id, None)

    def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        if not self.connected or not self.post_url:
            raise RuntimeError("Not connected")
            
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        try:
            self.client.post(self.post_url, json=msg, timeout=10.0)
        except Exception:
            pass

    def initialize(self) -> dict[str, Any]:
        result = self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-code-py", "version": "0.0.1"},
            },
        )
        self.send_notification("notifications/initialized")
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.send_request("tools/call", {"name": name, "arguments": arguments or {}})

    def list_resources(self) -> list[dict[str, Any]]:
        try:
            result = self.send_request("resources/list")
            return result.get("resources", [])
        except Exception:
            return []

    def read_resource(self, uri: str) -> dict[str, Any]:
        return self.send_request("resources/read", {"uri": uri})

    def close(self) -> None:
        self.connected = False
        try:
            self.client.close()
        except Exception:
            pass


def is_mcp_server_disabled(name: str, cwd: Path, home: Path | None = None) -> bool:
    from claude_code_py.services.mcp.state import is_mcp_server_disabled as _impl
    return _impl(name, cwd, home)


def set_mcp_server_disabled_state(name: str, disabled: bool, cwd: Path, home: Path | None = None) -> None:
    from claude_code_py.services.mcp.state import set_mcp_server_disabled_state as _impl
    _impl(name, disabled, cwd, home)


class McpManager:
    def __init__(self) -> None:
        self.clients: dict[str, McpProcessClient | McpHttpClient] = {}
        self.failures: dict[str, str] = {}

    def get_client(self, name: str) -> McpProcessClient | McpHttpClient | None:
        return self.clients.get(name)

    def initialize_all(self, configs: dict[str, dict[str, Any]]) -> None:
        self.failures.clear()
        for name, config in configs.items():
            if name in self.clients:
                continue
                
            command = config.get("command")
            url = config.get("url")
            type_val = config.get("type")
            
            if command:
                args = config.get("args", [])
                env = config.get("env")
                client = McpProcessClient(name, command, args, env)
            elif url or (type_val in {"http", "sse"}):
                if not url and type_val and type_val.startswith("http"):
                    url = type_val
                if not url:
                    self.failures[name] = "Missing URL for HTTP/SSE MCP server"
                    continue
                client = McpHttpClient(name, url)
            else:
                continue
                
            try:
                client.connect()
                client.initialize()
                self.clients[name] = client
            except (ConnectionError, TimeoutError) as e:
                # Clean, user-friendly error for connection issues
                self.failures[name] = str(e)
            except Exception as e:
                err_msg = str(e)
                # Simplify common errors
                if "10061" in err_msg or "actively refused" in err_msg:
                    self.failures[name] = f"Server not running ({url or command})"
                elif "10060" in err_msg or "timed out" in err_msg.lower():
                    self.failures[name] = f"Connection timed out ({url or command})"
                else:
                    self.failures[name] = err_msg[:200]

    def close_all(self) -> None:
        for client in list(self.clients.values()):
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()
        self.failures.clear()


mcp_manager = McpManager()

atexit.register(mcp_manager.close_all)


def initialize_mcp_servers(home: Path, cwd: Path) -> None:
    from claude_code_py.services.mcp.config import load_mcp_config
    from claude_code_py.tools.registry import Tool, tool_registry
    from claude_code_py.tools.builtins import register_builtin_tools

    # Clear previous tools and re-register builtins
    tool_registry.tools.clear()
    register_builtin_tools()

    # 1. Load MCP config
    configs = load_mcp_config(home, cwd)
    if not configs:
        return

    # Filter out disabled MCP servers before initialization
    active_configs = {}
    for name, cfg in configs.items():
        if not is_mcp_server_disabled(name, cwd, home):
            active_configs[name] = cfg

    # 2. Initialize all clients
    mcp_manager.initialize_all(active_configs)

    # 3. Register their tools in tool_registry
    for client_name, client in mcp_manager.clients.items():
        try:
            tools = client.list_tools()
            for mcp_tool in tools:
                name = mcp_tool["name"]
                if name in tool_registry.tools:
                    continue

                def make_mcp_handler(c=client, t_name=name):
                    def mcp_handler(**kwargs):
                        res = c.call_tool(t_name, kwargs)
                        return res.get("content", [])
                    return mcp_handler

                tool_registry.register(
                    Tool(
                        name=name,
                        description=mcp_tool.get("description", ""),
                        handler=make_mcp_handler(),
                        parameters_schema=mcp_tool.get("inputSchema", {"type": "object", "properties": {}}),
                    )
                )
        except Exception as e:
            print(f"Warning: Failed to list tools from MCP server '{client_name}': {e}")
