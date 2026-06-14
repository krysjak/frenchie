from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class PromptBundle:
    prompts: dict[str, str]

    def render_system_prompt(self, model: str) -> str:
        parts: list[str] = []
        for name in sorted(self.prompts):
            parts.append(f"# {name}")
            parts.append(self.prompts[name].rstrip())
            parts.append("")

        # Add active mode instructions
        from claude_code_py.services.state_store import StateStore
        try:
            mode = StateStore().load().get("permission_mode", "default")
        except Exception:
            mode = "default"

        parts.append("# Active Execution Mode")
        if mode == "plan":
            parts.append(
                "You are currently in PLAN MODE.\n"
                "In plan mode, your primary goal is to investigate the repository, design, outline, and document steps before editing files or executing commands.\n"
                "You should use read-only tools (Read, Glob, Grep, etc.) to understand the codebase.\n"
                "Do NOT use edit/write/execution tools unless absolutely necessary, and only after outline/planning. Every non-readonly tool will require explicit user confirmation.\n"
                "Focus on exploration, explaining options, and formulating plans."
            )
        elif mode == "auto":
            parts.append(
                "You are currently in AUTO MODE.\n"
                "In auto mode, all tool permissions are automatically approved. You can read, write, edit files and execute terminal commands without prompting the user.\n"
                "Proceed efficiently to accomplish the user's request."
            )
        else:
            parts.append(
                "You are currently in BUILD MODE.\n"
                "This is the default interactive mode where you can edit files and run commands. The user will be prompted to approve file modifications and shell commands unless they are in their always-allowed lists.\n"
                "Proceed with editing and building."
            )
        parts.append("")

        parts.append(f"Model: {model}")
        return "\n".join(parts).rstrip()


def load_prompt_bundle() -> PromptBundle:
    root = resources.files("claude_code_py").joinpath("resources", "prompts")
    prompts: dict[str, str] = {}
    for prompt_file in sorted(root.iterdir(), key=lambda p: p.name):
        if prompt_file.name.endswith(".md"):
            prompts[prompt_file.name] = prompt_file.read_text(encoding="utf-8")
    return PromptBundle(prompts=prompts)
