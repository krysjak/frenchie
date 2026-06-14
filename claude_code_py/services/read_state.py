from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ReadStateEntry:
    content: str
    timestamp: float
    offset: int | None = None
    limit: int | None = None


class ReadStateStore:
    def __init__(self, root: Path | None = None) -> None:
        from claude_code_py.services.config_store import project_dir
        self.path = (root or project_dir()) / "read_state.json"

    def load(self) -> dict[str, ReadStateEntry]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        return {key: ReadStateEntry(**value) for key, value in raw.items()}

    def save(self, entries: dict[str, ReadStateEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({key: asdict(value) for key, value in entries.items()}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def get(self, path: Path) -> ReadStateEntry | None:
        return self.load().get(str(path.resolve()))

    def set(self, path: Path, content: str, offset: int | None = None, limit: int | None = None) -> None:
        entries = self.load()
        entries[str(path.resolve())] = ReadStateEntry(
            content=content,
            timestamp=file_mtime(path),
            offset=offset,
            limit=limit,
        )
        self.save(entries)


def file_mtime(path: Path) -> float:
    return path.stat().st_mtime


def assert_read_before_write(path: Path) -> None:
    if not path.exists():
        return
    entry = ReadStateStore().get(path)
    if entry is None:
        raise ValueError("File has not been read yet. Read it first before writing to it.")
    if file_mtime(path) > entry.timestamp:
        raise ValueError("File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.")


def update_after_write(path: Path, content: str) -> None:
    ReadStateStore().set(path, content, offset=None, limit=None)
