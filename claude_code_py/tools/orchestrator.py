from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from claude_code_py.permissions import PermissionContext, decide_permission
from claude_code_py.tools import tool_registry
from claude_code_py.logger import get_logger


log = get_logger("orchestrator")


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


def extract_tool_uses(content: Any) -> list[ToolUse]:
    blocks = content if isinstance(content, list) else []
    tool_uses: list[ToolUse] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tool_uses.append(ToolUse(id=str(block["id"]), name=str(block["name"]), input=dict(block.get("input") or {})))
        elif getattr(block, "type", None) == "tool_use":
            tool_uses.append(ToolUse(id=str(block.id), name=str(block.name), input=dict(getattr(block, "input", {}) or {})))
    return tool_uses


def tool_result_block(tool_use_id: str, content: Any, is_error: bool = False) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        block["is_error"] = True
    return block


def run_tool_use(tool_use: ToolUse, permission_context: PermissionContext) -> dict[str, Any]:
    from claude_code_py.tui import prompt_permission, tool_spinner

    decision = decide_permission(tool_use.name, permission_context, json.dumps(tool_use.input, ensure_ascii=False))
    if decision.behavior == "ask":
        decision = prompt_permission(tool_use.name, tool_use.input, permission_context)

    if decision.behavior != "allow":
        log.warning("Tool '%s' denied — %s", tool_use.name, decision.message)
        return tool_result_block(tool_use.id, decision.message or "Permission denied", is_error=True)

    log.info("Running tool '%s' — input=%s", tool_use.name, _truncate(str(tool_use.input), 200))
    try:
        tool = tool_registry.get(tool_use.name)
        with tool_spinner(tool_use.name, tool_use.input) as state:
            try:
                result = tool.call(**tool_use.input)
                log.debug("Tool '%s' completed successfully", tool_use.name)
            except Exception as exc:
                log.error("Tool '%s' failed: %s", tool_use.name, exc)
                state["success"] = False
                state["error"] = str(exc)
                raise exc
        if isinstance(result, dict) and "_tool_result_content" in result:
            return tool_result_block(tool_use.id, result["_tool_result_content"])
        text = result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False)
        return tool_result_block(tool_use.id, text)
    except Exception as exc:
        log.exception("Unhandled error in tool '%s': %s", tool_use.name, exc)
        return tool_result_block(tool_use.id, str(exc), is_error=True)


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len - 3] + "..."


def run_tool_uses(tool_uses: list[ToolUse], permission_context: PermissionContext) -> list[dict[str, Any]]:
    return [run_tool_use(tool_use, permission_context) for tool_use in tool_uses]

