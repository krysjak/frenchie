"""Tests for the Skills Manager system."""

import json
import tempfile
from pathlib import Path

from claude_code_py.components.skills_manager import (
    Skill, SkillsManager,
)


def test_skill_dataclass() -> None:
    """Test Skill default values and construction."""
    skill = Skill(
        name="my-skill",
        description="A test skill",
        content="# My Skill\n\nDo something useful.",
        path=Path("/tmp/skills/my-skill/SKILL.md"),
    )
    assert skill.name == "my-skill"
    assert skill.description == "A test skill"
    assert skill.version == "1.0.0"
    assert skill.author == ""
    assert skill.tags == []


def test_skill_with_all_fields() -> None:
    skill = Skill(
        name="full-skill",
        description="Full test",
        content="content",
        path=Path("."),
        version="2.0.0",
        author="Frenchie",
        tags=["python", "test"],
    )
    assert skill.version == "2.0.0"
    assert skill.author == "Frenchie"
    assert skill.tags == ["python", "test"]


class TestSkillsManager:
    """Test SkillsManager with temporary directories."""

    def test_list_skills_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            skills = manager.list_skills()
            assert skills == []

    def test_create_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            skill = manager.create_skill(
                name="test-skill",
                content="# Hello World",
                description="A test skill",
            )
            assert skill.name == "test-skill"
            assert skill.description == "A test skill"
            assert skill.path.exists()

    def test_create_and_list_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("my-skill", "content", "desc")
            skills = manager.list_skills()
            assert len(skills) == 1
            assert skills[0].name == "my-skill"

    def test_get_skill_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("find-me", "content", "desc")
            skill = manager.get_skill("find-me")
            assert skill is not None
            assert skill.name == "find-me"

    def test_get_skill_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("MySkill", "content", "desc")
            skill = manager.get_skill("myskill")
            assert skill is not None

    def test_get_skill_nonexistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            assert manager.get_skill("nonexistent") is None

    def test_delete_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("delete-me", "content", "desc")
            assert manager.get_skill("delete-me") is not None
            result = manager.delete_skill("delete-me")
            assert result is True
            assert manager.get_skill("delete-me") is None

    def test_delete_nonexistent_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            assert manager.delete_skill("ghost") is False

    def test_export_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("export-me", "# Content", "Exported skill")
            output_path = Path(tmp) / "exported.skill.json"
            result = manager.export_skill("export-me", output_path)
            assert result is not None
            assert result.exists()
            data = json.loads(result.read_text())
            assert data["type"] == "skill"
            assert data["name"] == "export-me"

    def test_export_nonexistent_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            assert manager.export_skill("ghost") is None

    def test_import_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)

            # Create an export file
            export_data = {
                "type": "skill",
                "name": "imported-skill",
                "description": "Imported",
                "version": "1.0.0",
                "content": "# Imported Skill",
            }
            import_path = Path(tmp) / "import.skill.json"
            import_path.write_text(json.dumps(export_data), encoding="utf-8")

            skill = manager.import_skill(import_path)
            assert skill is not None
            assert skill.name == "imported-skill"

    def test_import_invalid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)

            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text('{"type": "not-a-skill"}', encoding="utf-8")

            skill = manager.import_skill(bad_path)
            assert skill is None  # Should fail type check

    def test_parse_metadata_with_frontmatter(self) -> None:
        content = "---\ndescription: My skill\nauthor: Tester\nversion: 2.0.0\ntags: python, cli\n---\n\n# Content"
        manager = SkillsManager(Path("/tmp"), Path("/tmp"))
        meta = manager._parse_metadata(content)
        assert meta.get("description") == "My skill"
        assert meta.get("author") == "Tester"
        assert meta.get("version") == "2.0.0"
        assert meta.get("tags") == ["python", "cli"]

    def test_parse_metadata_without_frontmatter(self) -> None:
        content = "# Just content\nNo frontmatter here."
        manager = SkillsManager(Path("/tmp"), Path("/tmp"))
        meta = manager._parse_metadata(content)
        assert meta == {}

    def test_list_multiple_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cwd = Path(tmp)
            manager = SkillsManager(home, cwd)
            manager.create_skill("skill-a", "content", "desc a")
            manager.create_skill("skill-b", "content", "desc b")
            skills = manager.list_skills()
            assert len(skills) == 2
            assert skills[0].name < skills[1].name  # Sorted alphabetically
