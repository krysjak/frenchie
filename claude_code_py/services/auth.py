from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from claude_code_py.services.config_store import get_config_value, set_config_value
from claude_code_py.services.claude_client import ClaudeClient, ClaudeClientError


def get_auth_token(home_dir: Path) -> str | None:
    # Check env var first
    token = os.environ.get("FRENCH_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if token:
        return token
    # Check stored config
    return get_config_value("api_key", home_dir)


def check_auth_status(home_dir: Path) -> dict[str, Any]:
    env_token = os.environ.get("FRENCH_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    config_token = get_config_value("api_key", home_dir)

    if env_token:
        return {"status": "authenticated", "source": "env"}
    elif config_token:
        return {"status": "authenticated", "source": "config"}
    else:
        return {"status": "unauthenticated", "source": None}


def login_user(api_key: str, home_dir: Path) -> bool:
    # Validate the key by instantiating a client and checking validity
    client = ClaudeClient(model="claude-3-5-sonnet", api_key=api_key)
    try:
        # Validate requires _client() to successfully initialize
        client.validate()
        set_config_value("api_key", api_key, home_dir)
        return True
    except ClaudeClientError:
        return False


def logout_user(home_dir: Path) -> None:
    set_config_value("api_key", None, home_dir)
