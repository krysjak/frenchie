from __future__ import annotations

import asyncio
import json
import logging
import websockets
from typing import Any

from claude_code_py.config import RuntimeConfig
from claude_code_py.query import run_single_turn

logger = logging.getLogger("claude_bridge")


class BridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 54321):
        self.host = host
        self.port = port
        self.server = None

    async def handle_connection(self, websocket: Any) -> None:
        logger.info("New IDE connection established")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "error": {"code": -32700, "message": "Parse error"},
                                "id": None,
                            }
                        )
                    )
                    continue

                if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "error": {"code": -32600, "message": "Invalid Request"},
                                "id": data.get("id") if isinstance(data, dict) else None,
                            }
                        )
                    )
                    continue

                method = data.get("method")
                params = data.get("params", {})
                req_id = data.get("id")

                if method == "send_message":
                    prompt = params.get("message", "")
                    if not prompt:
                        await websocket.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "error": {
                                        "code": -32602,
                                        "message": "Invalid params: 'message' is required",
                                    },
                                    "id": req_id,
                                }
                            )
                        )
                        continue

                    # Execute turn loop in executor
                    loop = asyncio.get_running_loop()
                    config = RuntimeConfig.from_environment()

                    def run() -> str:
                        return run_single_turn(config, prompt, stream=False)

                    try:
                        reply = await loop.run_in_executor(None, run)
                        await websocket.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "result": {"reply": reply},
                                    "id": req_id,
                                }
                            )
                        )
                    except Exception as e:
                        await websocket.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "error": {
                                        "code": -32603,
                                        "message": f"Internal error: {str(e)}",
                                    },
                                    "id": req_id,
                                }
                            )
                        )

                elif method == "status":
                    from claude_code_py.services.auth import check_auth_status

                    config = RuntimeConfig.from_environment()
                    auth = check_auth_status(config.home)
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "result": {
                                    "status": "connected",
                                    "model": config.model,
                                    "auth": auth["status"],
                                },
                                "id": req_id,
                            }
                        )
                    )

                else:
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32601,
                                    "message": f"Method not found: {method}",
                                },
                                "id": req_id,
                            }
                        )
                    )

        except websockets.exceptions.ConnectionClosed:
            logger.info("IDE connection closed")

    async def start(self) -> None:
        self.server = await websockets.serve(self.handle_connection, self.host, self.port)
        logger.info(f"Bridge server running on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
