from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


TaskStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: TaskStatus = "pending"
    activeForm: str | None = None
    owner: str | None = None
    blocks: list[str] = field(default_factory=list)
    blockedBy: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskStore:
    def __init__(self, root: Path | None = None) -> None:
        from claude_code_py.services.config_store import project_dir
        self.root = root or (project_dir() / "tasks")

    def _path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def create(
        self,
        subject: str,
        description: str,
        activeForm: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        self.root.mkdir(parents=True, exist_ok=True)
        task = Task(id=str(uuid4())[:8], subject=subject, description=description, activeForm=activeForm, metadata=metadata or {})
        self.save(task)
        return task

    def save(self, task: Task) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(task.id).write_text(json.dumps(asdict(task), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def get(self, task_id: str) -> Task | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        return Task(**json.loads(path.read_text(encoding="utf-8-sig")))

    def list(self) -> list[Task]:
        if not self.root.exists():
            return []
        return sorted((self.get(path.stem) for path in self.root.glob("*.json")), key=lambda task: task.id if task else "")

    def update(self, task_id: str, **updates: Any) -> tuple[Task | None, list[str]]:
        task = self.get(task_id)
        if not task:
            return None, []
        changed: list[str] = []
        if updates.get("status") == "deleted":
            self.delete(task_id)
            return task, ["deleted"]
        for field_name in ["subject", "description", "activeForm", "status", "owner"]:
            if field_name in updates and updates[field_name] is not None and getattr(task, field_name) != updates[field_name]:
                setattr(task, field_name, updates[field_name])
                changed.append(field_name)
        for relation in ["blocks", "blockedBy"]:
            add_key = "addBlocks" if relation == "blocks" else "addBlockedBy"
            for value in updates.get(add_key) or []:
                values = getattr(task, relation)
                if value not in values:
                    values.append(value)
                    changed.append(relation)
        if "metadata" in updates and updates["metadata"] is not None:
            for key, value in updates["metadata"].items():
                if value is None:
                    task.metadata.pop(key, None)
                else:
                    task.metadata[key] = value
            changed.append("metadata")
        self.save(task)
        return task, changed

    def delete(self, task_id: str) -> bool:
        path = self._path(task_id)
        if not path.exists():
            return False
        path.unlink()
        return True
