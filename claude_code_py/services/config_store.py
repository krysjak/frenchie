from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


# Name of the settings directory for this app. Kept separate from the real
# Claude Code (`.claude`) so the two never share state. Overridable via env
# (FRENCH_CONFIG_DIR_NAME, with the legacy CLAUDE_CONFIG_DIR_NAME as fallback).
CONFIG_DIR_NAME = (
    os.environ.get("FRENCH_CONFIG_DIR_NAME")
    or os.environ.get("CLAUDE_CONFIG_DIR_NAME")
    or ".frenchie"
)
CONFIG_FILE_NAME = "frenchie.json"
PROJECT_DIR_NAME = CONFIG_DIR_NAME

# Settings keys (kept in one place so renames don't drift across the codebase).
KEY_MODEL = "model"
KEY_PROVIDER = "provider"
KEY_BASE_URL = "base_url"
KEY_API_KEY = "api_key"

# Default settings seeded on first run: point the client at a local LM Studio
# server (OpenAI-compatible API) running the gemma-4-12b-it model.
DEFAULT_SETTINGS: dict[str, Any] = {
    KEY_MODEL: "gemma-4-12b-it",
    KEY_PROVIDER: "openai",
    KEY_BASE_URL: "http://localhost:1234/v1",
    KEY_API_KEY: "lm-studio",
}


def config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / CONFIG_DIR_NAME


def project_dir(cwd: Path | None = None) -> Path:
    """Per-project state directory (todos, tasks, teams, agents, ...)."""
    return (cwd or Path.cwd()) / PROJECT_DIR_NAME


def config_path(home: Path | None = None) -> Path:
    return config_dir(home) / CONFIG_FILE_NAME


def ensure_config_dir(home: Path | None = None) -> Path:
    """Create the config directory and seed default settings on first run."""
    directory = config_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path(home)
    if not path.exists():
        save_config(dict(DEFAULT_SETTINGS), home)
    return directory


def load_config(home: Path | None = None) -> dict[str, Any]:
    path = config_path(home)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_config(data: dict[str, Any], home: Path | None = None) -> Path:
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def set_config_value(key: str, value: Any, home: Path | None = None) -> Path:
    data = load_config(home)
    cursor: dict[str, Any] = data
    parts = key.split(".")
    for part in parts[:-1]:
        next_value = cursor.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise ValueError(f"Cannot set nested key through non-object value: {part}")
        cursor = next_value
    cursor[parts[-1]] = value
    return save_config(data, home)


def get_config_value(key: str, home: Path | None = None) -> Any:
    cursor: Any = load_config(home)
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


# ── Custom providers ───────────────────────────────────────────────────────

PROVIDERS_FILE_NAME = "providers.json"


def _providers_path(home: Path | None = None) -> Path:
    return config_dir(home) / PROVIDERS_FILE_NAME


def load_providers(home: Path | None = None) -> list[dict[str, Any]]:
    """Load custom providers from .frenchie/providers.json.

    Each provider dict has keys: id, title, base_url, api_key (optional),
    default_model (optional).
    """
    path = _providers_path(home)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        providers = data.get("providers", [])
        return providers if isinstance(providers, list) else []
    except Exception:
        return []


def save_providers(providers: list[dict[str, Any]], home: Path | None = None) -> Path:
    path = _providers_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"providers": providers}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def add_custom_provider(provider: dict[str, Any], home: Path | None = None) -> None:
    """Append a custom provider (must have 'id' and 'base_url')."""
    providers = load_providers(home)
    providers.append(provider)
    save_providers(providers, home)


def remove_custom_provider(provider_id: str, home: Path | None = None) -> bool:
    """Remove a custom provider by id. Returns True if removed."""
    providers = load_providers(home)
    new_providers = [p for p in providers if p.get("id") != provider_id]
    if len(new_providers) == len(providers):
        return False
    save_providers(new_providers, home)
    return True
