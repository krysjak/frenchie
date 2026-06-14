"""Skills Manager — Full skills CRUD system.

Inspired by the official Claude Code skills system with
list, view, create, edit, delete, import, and export capabilities.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from claude_code_py.components.dialog import confirm_dialog, input_dialog, notification_dialog
from claude_code_py.components.fuzzy_picker import fuzzy_picker


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED, ACCENT_CYAN,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


@dataclass
class Skill:
    """A skill with metadata."""
    name: str
    description: str
    content: str
    path: Path
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)


class SkillsManager:
    """Manager for discovering, creating, editing, and deleting skills."""

    def __init__(self, home: Path, cwd: Path):
        from claude_code_py.services.config_store import project_dir
        self.roots = [
            project_dir(cwd) / "skills",
            home / ".frenchie" / "skills",
            home / ".claude" / "skills",
            home / ".codex" / "skills",
        ]

    def _ensure_skill_dir(self) -> Path:
        """Ensure the primary skills directory exists."""
        primary = self.roots[0]
        primary.mkdir(parents=True, exist_ok=True)
        return primary

    def list_skills(self) -> list[Skill]:
        """List all available skills."""
        skills = []
        seen_names = set()

        for root in self.roots:
            if not root.exists():
                continue
            for skill_file in root.rglob("SKILL.md"):
                name = skill_file.parent.name
                if name in seen_names:
                    continue
                seen_names.add(name)
                content = skill_file.read_text(encoding="utf-8")
                meta = self._parse_metadata(content)
                skills.append(Skill(
                    name=name,
                    description=meta.get("description", ""),
                    content=content,
                    path=skill_file,
                    version=meta.get("version", "1.0.0"),
                    author=meta.get("author", ""),
                    tags=meta.get("tags", []),
                ))
        return sorted(skills, key=lambda s: s.name)

    def _parse_metadata(self, content: str) -> dict[str, Any]:
        """Parse YAML-like front matter from skill content."""
        meta: dict[str, Any] = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                front = content[3:end].strip()
                for line in front.splitlines():
                    if ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip()
                        if key == "tags":
                            meta["tags"] = [t.strip() for t in val.split(",")]
                        elif key == "version":
                            meta["version"] = val
                        elif key == "author":
                            meta["author"] = val
                        elif key == "description":
                            meta["description"] = val
        return meta

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        skills = self.list_skills()
        for skill in skills:
            if skill.name.lower() == name.lower():
                return skill
        return None

    def create_skill(self, name: str, content: str, description: str = "") -> Skill:
        """Create a new skill."""
        skill_dir = self._ensure_skill_dir() / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        full_content = content
        if description:
            if not content.startswith("---"):
                full_content = f"---\ndescription: {description}\n---\n\n{content}"

        skill_file.write_text(full_content, encoding="utf-8")
        return Skill(
            name=name,
            description=description,
            content=full_content,
            path=skill_file,
        )

    def edit_skill(self, name: str) -> bool:
        """Open a skill in the system editor."""
        skill = self.get_skill(name)
        if not skill:
            return False

        editor = (
            subprocess.os.environ.get("VISUAL")
            or subprocess.os.environ.get("EDITOR")
            or "nano"
        )
        try:
            subprocess.run([editor, str(skill.path)], check=False)
            return True
        except FileNotFoundError:
            notification_dialog("Error", f"No editor found. Set $EDITOR environment variable.", "error")
            return False

    def delete_skill(self, name: str) -> bool:
        """Delete a skill directory."""
        skill = self.get_skill(name)
        if not skill:
            return False
        skill_dir = skill.path.parent
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            return True
        return False

    def export_skill(self, name: str, output_path: Path | None = None) -> Path | None:
        """Export a skill to a portable format."""
        skill = self.get_skill(name)
        if not skill:
            return None

        export = {
            "type": "skill",
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "author": skill.author,
            "content": skill.content,
        }

        output = output_path or Path.cwd() / f"{skill.name}.skill.json"
        output.write_text(
            json.dumps(export, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return output

    def import_skill(self, import_path: Path) -> Skill | None:
        """Import a skill from a .skill.json file."""
        try:
            data = json.loads(import_path.read_text(encoding="utf-8-sig"))
            if data.get("type") != "skill":
                notification_dialog("Error", "Not a valid skill file.", "error")
                return None
            return self.create_skill(
                name=data.get("name", import_path.stem),
                content=data.get("content", ""),
                description=data.get("description", ""),
            )
        except (json.JSONDecodeError, Exception) as e:
            notification_dialog("Error", f"Failed to import skill: {e}", "error")
            return None


# ── Command Handlers ─────────────────────────────────────────────────────────

def skills_list_command(home: Path, cwd: Path) -> None:
    """List all skills."""
    manager = SkillsManager(home, cwd)
    skills = manager.list_skills()

    if not skills:
        console.print(Panel(
            Text("No skills found. Create one with /skills create.", style=TEXT_DIM),
            title=f"[bold {CLAUDE_ORANGE}]Skills[/bold {CLAUDE_ORANGE}]",
            border_style=CLAUDE_ORANGE,
            box=box.ROUNDED,
            expand=False,
        ))
        return

    table = Table(
        show_header=True,
        header_style=f"bold {CLAUDE_ORANGE}",
        padding=(0, 2),
        box=None,
    )
    table.add_column("Skill", style="bold")
    table.add_column("Version", width=10)
    table.add_column("Description")

    for skill in skills:
        table.add_row(skill.name, skill.version, skill.description)

    console.print(Panel(
        table,
        title=f"[bold {CLAUDE_ORANGE}]Skills ({len(skills)})[/bold {CLAUDE_ORANGE}]",
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
    ))


def skills_view_command(home: Path, cwd: Path, name: str | None = None) -> None:
    """View a skill's content."""
    manager = SkillsManager(home, cwd)

    if not name:
        skills = manager.list_skills()
        if not skills:
            console.print(f"  [{TEXT_DIM}]No skills found.[/]")
            return
        choices = [(s.name, s.description) for s in skills]
        selected = fuzzy_picker(choices, "Select a skill to view")
        if not selected:
            return
        name = selected

    skill = manager.get_skill(name)
    if not skill:
        console.print(f"  [{ACCENT_RED}]✘[/] Skill '{name}' not found.")
        return

    lines = skill.content.splitlines()
    display_lines = 30
    content = "\n".join(lines[:display_lines])
    if len(lines) > display_lines:
        content += f"\n  [{TEXT_DIM}]... and {len(lines) - display_lines} more lines[/]"

    panel = Panel(
        Text(content, style=TEXT_SECONDARY),
        title=f"[bold {CLAUDE_ORANGE}]Skill: {skill.name}[/bold {CLAUDE_ORANGE}]",
        subtitle=f"[{TEXT_DIM}]v{skill.version}[/]",
        border_style=CLAUDE_ORANGE,
        box=box.ROUNDED,
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)


def skills_create_command(home: Path, cwd: Path) -> None:
    """Create a new skill interactively."""
    name = input_dialog("Create Skill", "Enter skill name (slug):")
    if not name:
        return
    # Validate name
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).lower().strip("-")
    if not name:
        console.print(f"  [{ACCENT_RED}]✘[/] Invalid skill name.")
        return

    description = input_dialog("Description", "Brief description:", default="") or ""

    # Create the skill
    manager = SkillsManager(home, cwd)
    content = f"---\ndescription: {description}\nauthor: frenchie\nversion: 1.0.0\ntags: \n---\n\n# {name}\n\nDescribe what this skill does and how to use it.\n"
    skill = manager.create_skill(name, content, description)
    notification_dialog("Created", f"Skill '{skill.name}' created at {skill.path}", "success")

    # Open in editor
    if confirm_dialog("Edit Now?", "Open in editor to add content?"):
        manager.edit_skill(name)


def skills_edit_command(home: Path, cwd: Path, name: str | None = None) -> None:
    """Edit a skill."""
    manager = SkillsManager(home, cwd)

    if not name:
        skills = manager.list_skills()
        if not skills:
            console.print(f"  [{TEXT_DIM}]No skills to edit.[/]")
            return
        choices = [(s.name, s.description) for s in skills]
        selected = fuzzy_picker(choices, "Select a skill to edit")
        if not selected:
            return
        name = selected

    if manager.edit_skill(name):
        notification_dialog("Edited", f"Skill '{name}' saved.", "info")
    else:
        console.print(f"  [{ACCENT_RED}]✘[/] Failed to edit skill '{name}'.")


def skills_delete_command(home: Path, cwd: Path, name: str | None = None) -> None:
    """Delete a skill."""
    manager = SkillsManager(home, cwd)

    if not name:
        skills = manager.list_skills()
        if not skills:
            console.print(f"  [{TEXT_DIM}]No skills to delete.[/]")
            return
        choices = [(s.name, s.description) for s in skills]
        selected = fuzzy_picker(choices, "Select a skill to delete")
        if not selected:
            return
        name = selected

    if confirm_dialog("Delete Skill", f"Permanently delete skill '{name}'?", warn=True):
        if manager.delete_skill(name):
            notification_dialog("Deleted", f"Skill '{name}' deleted.", "info")
        else:
            console.print(f"  [{ACCENT_RED}]✘[/] Failed to delete skill '{name}'.")


def skills_export_command(home: Path, cwd: Path, name: str | None = None) -> None:
    """Export a skill to a file."""
    manager = SkillsManager(home, cwd)

    if not name:
        skills = manager.list_skills()
        if not skills:
            console.print(f"  [{TEXT_DIM}]No skills to export.[/]")
            return
        choices = [(s.name, s.description) for s in skills]
        selected = fuzzy_picker(choices, "Select a skill to export")
        if not selected:
            return
        name = selected

    path = manager.export_skill(name)
    if path:
        notification_dialog("Exported", f"Skill exported to {path}", "success")


def skills_import_command(home: Path, cwd: Path) -> None:
    """Import a skill from a file."""
    path_str = input_dialog(
        "Import Skill",
        "Path to .skill.json file:",
    )
    if not path_str:
        return
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        console.print(f"  [{ACCENT_RED}]✘[/] File not found: {path}")
        return

    manager = SkillsManager(home, cwd)
    skill = manager.import_skill(path)
    if skill:
        notification_dialog("Imported", f"Skill '{skill.name}' imported.", "success")
