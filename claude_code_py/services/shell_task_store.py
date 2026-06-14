from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from claude_code_py.services.task_store import Task, TaskStore


SHELL_TASK_TYPE = "local_shell"


def _is_windows() -> bool:
    return os.name == "nt"


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if _is_windows():
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    if _is_windows():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], text=True, capture_output=True, timeout=10)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def _tail(path: str | None, max_chars: int = 4000) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.exists():
        return ""
    data = file_path.read_bytes()
    if len(data) > max_chars:
        data = data[-max_chars:]
    return data.decode("utf-8", errors="replace")


class ShellTaskStore:
    def __init__(self, task_store: TaskStore | None = None) -> None:
        self.task_store = task_store or TaskStore()
        self.output_root = self.task_store.root.parent / "shell"

    def spawn(
        self,
        command: str,
        argv: list[str] | str,
        shell: bool,
        kind: str,
        cwd: Path | None = None,
        timeout_ms: int | None = None,
    ) -> Task:
        self.output_root.mkdir(parents=True, exist_ok=True)
        task = self.task_store.create(
            subject=command,
            description=f"{kind} background shell command",
            activeForm="running shell command",
            metadata={"_internal": False, "type": SHELL_TASK_TYPE, "kind": kind, "timeout_ms": timeout_ms},
        )
        stdout_path = self.output_root / f"{task.id}.stdout.log"
        stderr_path = self.output_root / f"{task.id}.stderr.log"
        stdout_handle = stdout_path.open("w", encoding="utf-8")
        stderr_handle = stderr_path.open("w", encoding="utf-8")
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if _is_windows() else 0
        start_new_session = not _is_windows()
        process = subprocess.Popen(
            argv,
            shell=shell,
            text=True,
            stdout=stdout_handle,
            stderr=stderr_handle,
            cwd=str(cwd) if cwd else None,
            creationflags=creationflags,
            start_new_session=start_new_session,
        )
        stdout_handle.close()
        stderr_handle.close()
        task.status = "in_progress"
        task.metadata.update(
            {
                "pid": process.pid,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "return_code": None,
            }
        )
        self.task_store.save(task)
        return task

    def refresh(self, task: Task) -> Task:
        if task.metadata.get("type") != SHELL_TASK_TYPE or task.status not in {"pending", "in_progress"}:
            return task
        pid = int(task.metadata.get("pid") or 0)
        if _pid_running(pid):
            return task
        task.status = "completed"
        task.metadata["return_code"] = task.metadata.get("return_code", 0)
        self.task_store.save(task)
        return task

    def stop(self, task_id: str) -> Task | None:
        task = self.task_store.get(task_id)
        if not task:
            return None
        if task.metadata.get("type") == SHELL_TASK_TYPE:
            pid = int(task.metadata.get("pid") or 0)
            if pid:
                _terminate_pid(pid)
        task.status = "cancelled"
        self.task_store.save(task)
        return task

    def summarize(self, task: Task) -> dict[str, Any]:
        task = self.refresh(task)
        return {
            "id": task.id,
            "subject": task.subject,
            "description": task.description,
            "status": task.status,
            "pid": task.metadata.get("pid"),
            "stdout_path": task.metadata.get("stdout_path"),
            "stderr_path": task.metadata.get("stderr_path"),
            "stdout_tail": _tail(task.metadata.get("stdout_path")),
            "stderr_tail": _tail(task.metadata.get("stderr_path")),
            "returnCode": task.metadata.get("return_code"),
        }
