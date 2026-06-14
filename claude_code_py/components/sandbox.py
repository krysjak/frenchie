"""Sandbox Mode — Docker container isolation for command execution.

Inspired by the official Claude Code sandbox system that provides
secure command execution in isolated containers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from claude_code_py.components.dialog import confirm_dialog, notification_dialog


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


@dataclass
class SandboxConfig:
    """Sandbox execution configuration."""
    image: str = "python:3.11-slim"
    timeout: int = 120
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    network: bool = False
    read_only_root: bool = True
    mount_cwd: bool = True
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """Result of a sandboxed command execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    error: str | None = None
    container_id: str | None = None


class SandboxManager:
    """Manager for sandboxed command execution via Docker."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def is_available(self) -> bool:
        """Check if sandbox execution is available."""
        return self._docker_available

    def run(
        self,
        command: str,
        cwd: Path | None = None,
        config: SandboxConfig | None = None,
    ) -> SandboxResult:
        """Run a command in a sandboxed Docker container."""
        cfg = config or self.config
        start = time.time()

        if not self._docker_available:
            return SandboxResult(
                error="Docker is not available. Install Docker to use sandbox mode.",
                duration=time.time() - start,
            )

        # Build docker run args
        docker_args = [
            "docker", "run",
            "--rm",
            "--network", "none" if not cfg.network else "bridge",
            "--memory", cfg.memory_limit,
            "--cpus", cfg.cpu_limit,
        ]

        if cfg.read_only_root:
            docker_args.append("--read-only")

        if cfg.mount_cwd:
            cwd_path = cwd or Path.cwd()
            docker_args.extend(["-v", f"{cwd_path}:/workspace:ro"])
            docker_args.extend(["-w", "/workspace"])

        # Environment variables
        for key, val in cfg.env_vars.items():
            docker_args.extend(["-e", f"{key}={val}"])

        # Add image and command
        docker_args.append(cfg.image)
        docker_args.extend(["sh", "-c", command])

        try:
            result = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=cfg.timeout,
            )
            return SandboxResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                error=f"Command timed out after {cfg.timeout}s",
                stdout="",
                stderr="",
                exit_code=-1,
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return SandboxResult(
                error="Docker command not found.",
                duration=time.time() - start,
            )
        except Exception as e:
            return SandboxResult(
                error=str(e),
                duration=time.time() - start,
            )

    def check_environment(self) -> list[dict[str, Any]]:
        """Check if sandbox environment is properly configured."""
        checks = []

        # Docker availability
        if self._docker_available:
            checks.append({"check": "Docker installed", "status": "ok", "detail": ""})
        else:
            checks.append({
                "check": "Docker installed",
                "status": "error",
                "detail": "Install Docker Desktop or Docker Engine",
            })

        # Test image pull
        if self._docker_available:
            try:
                pull = subprocess.run(
                    ["docker", "pull", self.config.image],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if pull.returncode == 0:
                    checks.append({"check": f"Image {self.config.image}", "status": "ok", "detail": ""})
                else:
                    checks.append({
                        "check": f"Image {self.config.image}",
                        "status": "error",
                        "detail": pull.stderr[:100],
                    })
            except Exception as e:
                checks.append({
                    "check": f"Image {self.config.image}",
                    "status": "error",
                    "detail": str(e),
                })

        # Memory/cpu settings
        if self._docker_available:
            try:
                info = subprocess.run(
                    ["docker", "info", "--format", "{{json .}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if info.returncode == 0:
                    data = json.loads(info.stdout)
                    checks.append({"check": "Docker resources", "status": "ok", "detail": ""})
            except Exception:
                pass

        return checks


# ── Global singleton ─────────────────────────────────────────────────────────
_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager


# ── Command Handlers ─────────────────────────────────────────────────────────

def sandbox_run_command(command: str, cwd: Path | None = None) -> None:
    """Run a command in the sandbox."""
    manager = get_sandbox_manager()
    if not manager.is_available():
        notification_dialog("Sandbox Unavailable",
            "Docker is required for sandbox mode. Install Docker Desktop and try again.",
            "error")
        return

    console.print(f"  [{CLAUDE_DIM}]Running in sandbox ({manager.config.image})...[/]")
    result = manager.run(command, cwd=cwd)

    if result.stdout:
        console.print(f"  [{TEXT_SECONDARY}]stdout:[/]")
        for line in result.stdout.splitlines()[:30]:
            console.print(f"    {line}")
        if len(result.stdout.splitlines()) > 30:
            console.print(f"    [{TEXT_DIM}]... ({len(result.stdout.splitlines()) - 30} more lines)[/]")

    if result.stderr:
        console.print(f"  [{ACCENT_YELLOW}]stderr:[/]")
        for line in result.stderr.splitlines()[:10]:
            console.print(f"    [{TEXT_DIM}]{line}[/]")

    if result.error:
        console.print(f"  [{ACCENT_RED}]✘ Error: {result.error}[/]")
    else:
        status = ACCENT_GREEN if result.exit_code == 0 else ACCENT_YELLOW
        console.print(f"  [{status}]✔[/] Exit code: {result.exit_code}  [{TEXT_DIM}]{result.duration:.1f}s[/]")


def sandbox_check_command() -> None:
    """Check sandbox environment."""
    manager = get_sandbox_manager()
    checks = manager.check_environment()

    all_ok = all(c["status"] == "ok" for c in checks)
    console.print(Panel(
        "\n".join(
            f"  [{ACCENT_GREEN if c['status'] == 'ok' else ACCENT_RED}]"
            f"{'✔' if c['status'] == 'ok' else '✘'}[/] {c['check']}"
            f"  [{TEXT_DIM}]{c['detail']}[/]"
            for c in checks
        ),
        title=f"[bold {CLAUDE_ORANGE}]Sandbox Check[/bold {CLAUDE_ORANGE}]",
        subtitle=f"[{ACCENT_GREEN if all_ok else ACCENT_YELLOW}]"
                 f"{'All checks passed' if all_ok else 'Issues found'}[/]",
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
    ))
