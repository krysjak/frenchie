from __future__ import annotations

from pathlib import Path
from typing import Any


def _skill_roots() -> list[Path]:
    from claude_code_py.services.config_store import project_dir
    roots = [project_dir() / "skills", Path.home() / ".codex" / "skills"]
    return [root for root in roots if root.exists()]


def _find_skill(name: str) -> Path | None:
    for root in _skill_roots():
        for candidate in root.rglob("SKILL.md"):
            if candidate.parent.name.lower() == name.lower():
                return candidate
    return None


def skill(skill: str, args: str | None = None, **_: Any) -> dict[str, Any]:
    path = _find_skill(skill)
    if not path:
        available = sorted(candidate.parent.name for root in _skill_roots() for candidate in root.rglob("SKILL.md"))
        return {"success": False, "message": f"Skill not found: {skill}", "available": available}
    content = path.read_text(encoding="utf-8")
    return {"success": True, "skill": skill, "args": args or "", "content": content, "path": str(path)}
