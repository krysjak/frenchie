from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Literal


PermissionMode = Literal["acceptEdits", "bypassPermissions", "default", "dontAsk", "plan", "auto", "bubble"]
PermissionBehavior = Literal["allow", "deny", "ask"]


READ_ONLY_TOOLS = {
    "Read",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "TaskGet",
    "TaskList",
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    "EnterPlanMode",
    "ToolSearch",
    "Skill",
}
EDIT_TOOLS = {
    "Write",
    "Edit",
    "TodoWrite",
    "TaskCreate",
    "TaskUpdate",
    "TaskStop",
    "ExitPlanMode",
    "Config",
    "NotebookEdit",
    "Agent",
    "TeamCreate",
    "TeamDelete",
    "SendMessage",
}
SHELL_TOOLS = {"Bash", "PowerShell"}


@dataclass(frozen=True)
class PermissionRuleValue:
    tool_name: str
    rule_content: str | None = None

    def matches(self, tool_name: str, summary: str = "") -> bool:
        if not fnmatch.fnmatch(tool_name, self.tool_name):
            return False
        if self.rule_content is None:
            return True
        return fnmatch.fnmatch(summary, self.rule_content)


@dataclass
class PermissionContext:
    mode: PermissionMode = "default"
    always_allow: list[PermissionRuleValue] = field(default_factory=list)
    always_deny: list[PermissionRuleValue] = field(default_factory=list)
    always_ask: list[PermissionRuleValue] = field(default_factory=list)
    should_avoid_permission_prompts: bool = False


@dataclass(frozen=True)
class PermissionDecision:
    behavior: PermissionBehavior
    message: str = ""


def permission_mode_from_string(value: str | None) -> PermissionMode:
    allowed = {"acceptEdits", "bypassPermissions", "default", "dontAsk", "plan", "auto", "bubble"}
    return value if value in allowed else "default"  # type: ignore[return-value]


def decide_permission(tool_name: str, context: PermissionContext, summary: str = "") -> PermissionDecision:
    from claude_code_py.services.state_store import StateStore
    try:
        context.mode = StateStore().load().get("permission_mode", "default")
    except Exception:
        pass

    for rule in context.always_deny:
        if rule.matches(tool_name, summary):
            return PermissionDecision("deny", f"Denied by rule: {tool_name}")
    for rule in context.always_allow:
        if rule.matches(tool_name, summary):
            return PermissionDecision("allow", f"Allowed by rule: {tool_name}")
    for rule in context.always_ask:
        if rule.matches(tool_name, summary):
            return PermissionDecision("ask", f"Ask required by rule: {tool_name}")

    if tool_name == "Config" and '"value"' not in summary:
        return PermissionDecision("allow", "Config read")
    if tool_name in READ_ONLY_TOOLS:
        return PermissionDecision("allow", "Read-only tool")
    if context.mode in ("bypassPermissions", "auto"):
        return PermissionDecision("allow", "Bypass permissions mode")
    if context.mode == "acceptEdits" and tool_name in EDIT_TOOLS:
        return PermissionDecision("allow", "Accept edits mode")
    if context.mode == "dontAsk":
        return PermissionDecision("deny", "Permission prompts disabled")
    if context.mode == "plan" and tool_name in EDIT_TOOLS | SHELL_TOOLS:
        return PermissionDecision("ask", "Plan mode requires approval")
    if context.should_avoid_permission_prompts:
        return PermissionDecision("deny", "Permission prompts unavailable")
    return PermissionDecision("ask", f"Permission required for {tool_name}")
