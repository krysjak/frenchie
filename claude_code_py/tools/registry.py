from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    read_only: bool = False
    aliases: tuple[str, ...] = ()

    def call(self, **kwargs: Any) -> Any:
        return self.handler(**kwargs)


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool
        for alias in tool.aliases:
            self.tools[alias] = tool

    def names(self) -> list[str]:
        return sorted({tool.name for tool in self.tools.values()})

    def get(self, name: str) -> Tool:
        return self.tools[name]

    def api_schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tool in self.tools.values():
            if tool.name in seen:
                continue
            seen.add(tool.name)
            schemas.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters_schema or {"type": "object", "properties": {}},
                }
            )
        return schemas


tool_registry = ToolRegistry()
