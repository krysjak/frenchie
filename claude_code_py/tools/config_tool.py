from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_code_py.services.config_store import get_config_value, set_config_value


SUPPORTED_SETTINGS = {
    "theme",
    "model",
    "editorMode",
    "verbose",
    "permissions.defaultMode",
    "remoteControlAtStartup",
}


def config_tool(setting: str, value: str | bool | int | float | None = None) -> dict[str, Any]:
    home = Path.home()
    if setting not in SUPPORTED_SETTINGS:
        return {"success": False, "error": f'Unknown setting: "{setting}"'}
    if value is None:
        return {"success": True, "operation": "get", "setting": setting, "value": get_config_value(setting, home)}
    previous = get_config_value(setting, home)
    set_config_value(setting, value, home)
    return {
        "success": True,
        "operation": "set",
        "setting": setting,
        "previousValue": previous,
        "newValue": value,
    }
