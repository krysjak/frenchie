from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class TeamMember:
    agentId: str
    name: str
    agentType: str
    model: str | None = None
    joinedAt: int | None = None
    cwd: str | None = None
    subscriptions: list[str] = field(default_factory=list)


@dataclass
class Team:
    name: str
    description: str | None
    createdAt: int
    leadAgentId: str
    members: list[TeamMember]


class TeamStore:
    def __init__(self, root: Path | None = None) -> None:
        from claude_code_py.services.config_store import project_dir
        self.root = root or (project_dir() / "teams")

    def _path(self, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-") or "team"
        return self.root / f"{safe}.json"

    def create(self, name: str, description: str | None = None, agent_type: str | None = None) -> Team:
        import time

        self.root.mkdir(parents=True, exist_ok=True)
        final_name = name
        if self._path(final_name).exists():
            final_name = f"{name}-{str(uuid4())[:4]}"
        lead_id = f"lead-{final_name}"
        team = Team(
            name=final_name,
            description=description,
            createdAt=int(time.time() * 1000),
            leadAgentId=lead_id,
            members=[TeamMember(agentId=lead_id, name="lead", agentType=agent_type or "lead", cwd=str(Path.cwd()))],
        )
        self._path(final_name).write_text(json.dumps(asdict(team), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return team

    def read(self, name: str) -> Team | None:
        path = self._path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        data["members"] = [TeamMember(**member) for member in data.get("members", [])]
        return Team(**data)

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self) -> list[Team]:
        if not self.root.exists():
            return []
        teams: list[Team] = []
        for path in self.root.glob("*.json"):
            team = self.read(path.stem)
            if team:
                teams.append(team)
        return teams

    def mailbox_path(self, recipient: str, team_name: str | None = None) -> Path:
        root = self.root / (team_name or "default") / "mailboxes"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{recipient}.jsonl"

    def send_message(self, recipient: str, message: dict[str, Any], team_name: str | None = None) -> Path:
        path = self.mailbox_path(recipient, team_name)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
        return path
