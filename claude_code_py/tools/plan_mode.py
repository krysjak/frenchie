from __future__ import annotations

from claude_code_py.services.state_store import StateStore


def enter_plan_mode() -> dict[str, str]:
    StateStore().set("permission_mode", "plan")
    return {"message": "Entered plan mode. Focus on exploration and design before editing files."}


def exit_plan_mode(allowedPrompts: list[dict[str, str]] | None = None, **_: object) -> dict[str, object]:
    store = StateStore()
    state = store.load()
    if state.get("permission_mode") != "plan":
        raise ValueError("You are not in plan mode.")
    state["permission_mode"] = "default"
    state["allowedPrompts"] = allowedPrompts or []
    store.save(state)
    return {"plan": None, "isAgent": False, "allowedPrompts": allowedPrompts or []}
