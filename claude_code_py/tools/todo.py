from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def todo_write(todos: list[dict[str, Any]], file_path: str | None = None, **_: Any) -> dict[str, Any]:
    from claude_code_py.services.config_store import project_dir
    target = Path(file_path).expanduser() if file_path else project_dir() / "todos.json"
    if not target.is_absolute():
        target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(todos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"file_path": str(target), "count": len(todos)}
