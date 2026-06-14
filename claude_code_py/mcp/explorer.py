from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def default_src_root() -> Path:
    configured = os.environ.get("CLAUDE_CODE_SRC_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3] / "src"


@dataclass
class ClaudeCodeExplorer:
    src_root: Path

    @classmethod
    def from_environment(cls) -> "ClaudeCodeExplorer":
        return cls(default_src_root().resolve())

    def validate_src_root(self) -> None:
        if not self.src_root.exists() or not self.src_root.is_dir():
            raise FileNotFoundError(f"Source root not found: {self.src_root}")

    def safe_path(self, rel_path: str) -> Path:
        resolved = (self.src_root / rel_path).resolve()
        if self.src_root not in (resolved, *resolved.parents):
            raise ValueError("Invalid path")
        return resolved

    def list_dir(self, rel_path: str = "") -> list[str]:
        directory = self.safe_path(rel_path)
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        entries = [entry.name + ("/" if entry.is_dir() else "") for entry in directory.iterdir()]
        return sorted(entries)

    def walk_files(self, rel_path: str = "") -> list[str]:
        root = self.safe_path(rel_path)
        files: list[str] = []
        for path in root.rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(self.src_root)).replace("\\", "/"))
        return sorted(files)

    def get_tool_list(self) -> list[dict[str, Any]]:
        tools_dir = self.safe_path("tools")
        tools: list[dict[str, Any]] = []
        for entry in tools_dir.iterdir():
            if not entry.is_dir() or entry.name in {"shared", "testing"}:
                continue
            files = self.list_dir(f"tools/{entry.name}")
            tools.append({"name": entry.name, "directory": f"tools/{entry.name}", "files": files})
        return sorted(tools, key=lambda item: item["name"])

    def get_command_list(self) -> list[dict[str, Any]]:
        commands_dir = self.safe_path("commands")
        commands: list[dict[str, Any]] = []
        for entry in commands_dir.iterdir():
            if entry.is_dir():
                commands.append(
                    {
                        "name": entry.name,
                        "path": f"commands/{entry.name}",
                        "isDirectory": True,
                        "files": self.list_dir(f"commands/{entry.name}"),
                    }
                )
            else:
                commands.append(
                    {
                        "name": re.sub(r"\.(ts|tsx|js)$", "", entry.name),
                        "path": f"commands/{entry.name}",
                        "isDirectory": False,
                    }
                )
        return sorted(commands, key=lambda item: item["name"])

    def read_source_file(self, rel_path: str, start_line: int = 1, end_line: int | None = None) -> str:
        path = self.safe_path(rel_path)
        if not path.is_file():
            raise FileNotFoundError(rel_path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        end = end_line or len(lines)
        selected = lines[max(0, start_line - 1) : min(len(lines), end)]
        return "\n".join(f"{start_line + index:>5} | {line}" for index, line in enumerate(selected))

    def get_tool_source(self, tool_name: str, file_name: str | None = None) -> str:
        tool_dir = self.safe_path(f"tools/{tool_name}")
        if not tool_dir.is_dir():
            raise FileNotFoundError(f"Tool not found: {tool_name}")
        if not file_name:
            files = self.list_dir(f"tools/{tool_name}")
            file_name = next((f for f in files if f in {f"{tool_name}.ts", f"{tool_name}.tsx"}), None)
            file_name = file_name or next((f for f in files if f.endswith((".ts", ".tsx", ".js"))), None)
        if not file_name:
            raise FileNotFoundError(f"No source files in {tool_name}")
        rel_path = f"tools/{tool_name}/{file_name.rstrip('/')}"
        path = self.safe_path(rel_path)
        if not path.is_file():
            raise FileNotFoundError(rel_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        return f"// {rel_path}\n// {len(content.splitlines())} lines\n\n{content}"

    def get_command_source(self, command_name: str, file_name: str | None = None) -> str:
        candidates = [f"commands/{command_name}", f"commands/{command_name}.ts", f"commands/{command_name}.tsx"]
        found: Path | None = None
        for candidate in candidates:
            path = self.safe_path(candidate)
            if path.exists():
                found = path
                break
        if not found:
            raise FileNotFoundError(f"Command not found: {command_name}")
        if found.is_file():
            return found.read_text(encoding="utf-8", errors="replace")
        if file_name:
            return self.safe_path(f"commands/{command_name}/{file_name}").read_text(encoding="utf-8", errors="replace")
        files = self.list_dir(f"commands/{command_name}")
        return "Command: " + command_name + "\nFiles:\n" + "\n".join(f"  {name}" for name in files)

    def search_source(self, pattern: str, file_pattern: str | None = None, max_results: int = 50) -> str:
        regex = re.compile(pattern, re.IGNORECASE)
        matches: list[str] = []
        for rel_path in self.walk_files():
            if len(matches) >= max_results:
                break
            if file_pattern and not rel_path.endswith(file_pattern):
                continue
            text = self.safe_path(rel_path).read_text(encoding="utf-8", errors="ignore")
            for number, line in enumerate(text.splitlines(), start=1):
                if len(matches) >= max_results:
                    break
                if regex.search(line):
                    matches.append(f"{rel_path}:{number}: {line.strip()}")
        return f"Found {len(matches)} match(es):\n\n" + "\n".join(matches) if matches else "No matches found."

    def get_architecture(self) -> str:
        top_level = self.list_dir()
        tools = self.get_tool_list()
        commands = self.get_command_list()
        return "\n".join(
            [
                "# Frenchie Architecture Overview",
                "",
                "## Source Root",
                str(self.src_root),
                "",
                "## Top-Level Entries",
                *[f"- {entry}" for entry in top_level],
                "",
                f"## Agent Tools ({len(tools)})",
                *[f"- **{tool['name']}** - {len(tool['files'])} files: {', '.join(tool['files'])}" for tool in tools],
                "",
                f"## Slash Commands ({len(commands)})",
                *[
                    f"- **{command['name']}** {'(directory)' if command['isDirectory'] else '(file)'}"
                    for command in commands
                ],
            ]
        )

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if name == "list_tools":
            text = json.dumps(self.get_tool_list(), indent=2, ensure_ascii=False)
        elif name == "list_commands":
            text = json.dumps(self.get_command_list(), indent=2, ensure_ascii=False)
        elif name == "get_tool_source":
            text = self.get_tool_source(str(args.get("toolName", "")), args.get("fileName"))
        elif name == "get_command_source":
            text = self.get_command_source(str(args.get("commandName", "")), args.get("fileName"))
        elif name == "read_source_file":
            text = self.read_source_file(str(args.get("path", "")), int(args.get("startLine", 1)), args.get("endLine"))
        elif name == "search_source":
            text = self.search_source(str(args.get("pattern", "")), args.get("filePattern"), int(args.get("maxResults", 50)))
        elif name == "list_directory":
            text = "\n".join(self.list_dir(str(args.get("path", ""))))
        elif name == "get_architecture":
            text = self.get_architecture()
        else:
            raise ValueError(f"Unknown tool: {name}")
        return {"content": [{"type": "text", "text": text}]}

    def list_mcp_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "list_tools", "description": "List all Frenchie agent tools.", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "list_commands", "description": "List all Frenchie slash commands.", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_tool_source", "description": "Read a tool implementation.", "inputSchema": {"type": "object"}},
            {"name": "get_command_source", "description": "Read a command implementation.", "inputSchema": {"type": "object"}},
            {"name": "read_source_file", "description": "Read a source file by relative path.", "inputSchema": {"type": "object"}},
            {"name": "search_source", "description": "Search source files.", "inputSchema": {"type": "object"}},
            {"name": "list_directory", "description": "List files and directories under src.", "inputSchema": {"type": "object"}},
            {"name": "get_architecture", "description": "Get architecture overview.", "inputSchema": {"type": "object", "properties": {}}},
        ]
