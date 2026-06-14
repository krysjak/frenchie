from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, root: Path | None = None) -> None:
        from claude_code_py.services.config_store import project_dir
        self.path = (root or project_dir()) / "state.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8-sig"))

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def set(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)
