from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Frenchie Web Dashboard")
logger = logging.getLogger("frenchie_web_server")

# Global session store
sessions: dict[str, WebSocket] = {}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "activeSessions": len(sessions),
        "authProvider": "none",
    }


@app.get("/api/sessions")
async def get_sessions() -> list[str]:
    return list(sessions.keys())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    session_id = str(uuid.uuid4())
    sessions[session_id] = websocket

    cmd = [sys.executable, "-m", "claude_code_py"]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )

    await websocket.send_json({"type": "session", "token": session_id})

    async def read_from_process() -> None:
        try:
            while True:
                # Read chunks of output from process stdout
                data = await process.stdout.read(1024)
                if not data:
                    break
                await websocket.send_text(data.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.error(f"Error reading stdout: {e}")
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    async def read_from_websocket() -> None:
        try:
            while True:
                msg = await websocket.receive_text()
                try:
                    parsed = json.loads(msg)
                    if isinstance(parsed, dict) and parsed.get("type") == "input":
                        stdin_data = parsed.get("data", "")
                        process.stdin.write(stdin_data.encode("utf-8"))
                        await process.stdin.drain()
                except json.JSONDecodeError:
                    process.stdin.write(msg.encode("utf-8"))
                    await process.stdin.drain()
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if process.returncode is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    read_task = asyncio.create_task(read_from_process())
    write_task = asyncio.create_task(read_from_websocket())

    await asyncio.gather(read_task, write_task, return_exceptions=True)
    sessions.pop(session_id, None)


# Serve static files from web/out if exists
web_out_path = Path(__file__).resolve().parents[2] / "web" / "out"
if web_out_path.exists():
    app.mount("/", StaticFiles(directory=str(web_out_path), html=True), name="static")
