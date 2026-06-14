from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from claude_code_py.config import RuntimeConfig


CommandType = Literal["local", "prompt", "local-jsx"]


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: Callable[..., Any]
    type: CommandType = "local"
    aliases: tuple[str, ...] = ()
    supports_non_interactive: bool = True
    immediate: bool = False
    hidden: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, name: str) -> bool:
        return self.name == name or name in self.aliases

    def call(self, config: RuntimeConfig, *args: Any) -> Any:
        return self.handler(config, *args)
