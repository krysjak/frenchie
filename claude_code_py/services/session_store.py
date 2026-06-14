from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from claude_code_py.messages import Message


def project_slug(cwd: Path) -> str:
    return str(cwd.resolve()).replace(":", "").replace("\\", "-").replace("/", "-").strip("-")


class SessionStore:
    def __init__(self, home: Path, cwd: Path, session_id: str | None = None) -> None:
        self.home = home
        self.cwd = cwd
        self.session_id = session_id or str(uuid4())
        from claude_code_py.services.config_store import config_dir
        self.project_dir = config_dir(home) / "projects" / project_slug(cwd)
        self.path = self.project_dir / f"{self.session_id}.jsonl"

    def append(self, message: Message) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.to_json(), ensure_ascii=False) + "\n")

    def load(self) -> list[Message]:
        if not self.path.exists():
            return []
        messages: list[Message] = []
        for line in self.path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                messages.append(Message.from_json(json.loads(line)))
        return messages

    def list_sessions(self) -> list[Path]:
        if not self.project_dir.exists():
            return []
        return sorted(self.project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
