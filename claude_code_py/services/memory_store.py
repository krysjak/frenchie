from __future__ import annotations

import os
import subprocess
from pathlib import Path


MEMORY_FILE_NAME = "FRENCHIE.md"


def project_memory_path(cwd: Path | None = None) -> Path:
    return (cwd or Path.cwd()) / MEMORY_FILE_NAME


def user_memory_path(home: Path | None = None) -> Path:
    from claude_code_py.services.config_store import config_dir
    return config_dir(home) / MEMORY_FILE_NAME


def list_memory_files(cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    candidates = [project_memory_path(cwd), user_memory_path(home)]
    return candidates


def ensure_memory_file(scope: str, cwd: Path | None = None, home: Path | None = None) -> Path:
    path = user_memory_path(home) if scope == "user" else project_memory_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return path


def open_in_editor(path: Path) -> int:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        return -1
    completed = subprocess.run([editor, str(path)], check=False)
    return completed.returncode
