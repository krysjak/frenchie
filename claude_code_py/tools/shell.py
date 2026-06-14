from __future__ import annotations

import subprocess
from typing import Any

from claude_code_py.services.shell_task_store import ShellTaskStore

from .shell_safety import validate_shell_command


def bash(
    command: str,
    timeout_ms: int = 120000,
    run_in_background: bool = False,
    dangerouslyDisableSandbox: bool = False,
    **_: Any,
) -> dict[str, Any]:
    validate_shell_command(command, allow_destructive=dangerouslyDisableSandbox)
    if run_in_background:
        task = ShellTaskStore().spawn(command=command, argv=command, shell=True, kind="bash", timeout_ms=timeout_ms)
        return {
            "task_id": task.id,
            "shell_id": task.id,
            "pid": task.metadata.get("pid"),
            "status": task.status,
            "message": "Command started in background. Use TaskGet or TaskStop with this task_id.",
            "stdout_path": task.metadata.get("stdout_path"),
            "stderr_path": task.metadata.get("stderr_path"),
        }
    try:
        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_ms / 1000,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "interrupted": True,
            "message": f"Command timed out after {timeout_ms}ms",
        }
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "interrupted": False,
    }


def powershell(
    command: str,
    timeout: int | None = None,
    timeout_ms: int | None = None,
    run_in_background: bool = False,
    dangerouslyDisableSandbox: bool = False,
    **_: Any,
) -> dict[str, Any]:
    validate_shell_command(command, allow_destructive=dangerouslyDisableSandbox)
    effective_timeout = timeout_ms if timeout_ms is not None else timeout if timeout is not None else 120000
    argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    if run_in_background:
        task = ShellTaskStore().spawn(command=command, argv=argv, shell=False, kind="powershell", timeout_ms=effective_timeout)
        return {
            "task_id": task.id,
            "shell_id": task.id,
            "pid": task.metadata.get("pid"),
            "status": task.status,
            "message": "PowerShell command started in background. Use TaskGet or TaskStop with this task_id.",
            "stdout_path": task.metadata.get("stdout_path"),
            "stderr_path": task.metadata.get("stderr_path"),
        }
    try:
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=effective_timeout / 1000,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "interrupted": True,
            "returnCode": None,
            "message": f"Command timed out after {effective_timeout}ms",
        }
    return {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "interrupted": False,
        "returnCode": completed.returncode,
    }
