from __future__ import annotations

from dataclasses import asdict
from typing import Any

from claude_code_py.services.team_store import TeamStore


def team_create(team_name: str, description: str | None = None, agent_type: str | None = None) -> dict[str, str]:
    team = TeamStore().create(team_name, description, agent_type)
    return {"team_name": team.name, "team_file_path": str(TeamStore()._path(team.name)), "lead_agent_id": team.leadAgentId}


def team_delete(team_name: str | None = None) -> dict[str, Any]:
    store = TeamStore()
    target = team_name
    if not target:
        teams = store.list()
        target = teams[0].name if teams else None
    if not target:
        return {"success": True, "message": "No team name found, nothing to clean up"}
    deleted = store.delete(target)
    return {"success": deleted, "message": f'Cleaned up team "{target}"' if deleted else f'Team "{target}" not found', "team_name": target}


def send_message(to: str, message: str | dict[str, Any], summary: str | None = None, team_name: str | None = None) -> dict[str, Any]:
    content = message if isinstance(message, str) else message
    path = TeamStore().send_message(to, {"from": "lead", "text": content, "summary": summary}, team_name)
    return {"success": True, "message": f"Message sent to {to}'s inbox", "routing": {"sender": "lead", "target": f"@{to}", "summary": summary, "content": content}, "mailbox": str(path)}
