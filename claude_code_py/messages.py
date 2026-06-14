from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4


MessageType = Literal["user", "assistant", "system", "progress", "attachment"]
SystemLevel = Literal["info", "warning", "error"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Message:
    type: MessageType
    uuid: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=now_iso)
    content: Any = ""
    subtype: str | None = None
    level: SystemLevel | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Message":
        return cls(**data)


def create_user_message(content: str | list[dict[str, Any]]) -> Message:
    return Message(type="user", content={"role": "user", "content": content})


def create_assistant_message(content: str | list[dict[str, Any]], request_id: str | None = None) -> Message:
    metadata = {"request_id": request_id} if request_id else {}
    return Message(type="assistant", content={"role": "assistant", "content": content}, metadata=metadata)


def create_system_message(content: str, level: SystemLevel = "info", subtype: str = "informational") -> Message:
    return Message(type="system", content=content, level=level, subtype=subtype)


def normalize_for_api(messages: list[Message]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if message.type not in {"user", "assistant"}:
            continue
        if isinstance(message.content, dict) and "role" in message.content:
            normalized.append(message.content)
    return normalized
