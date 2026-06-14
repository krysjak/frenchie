from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    cwd: Path
    home: Path
    model: str
    is_remote: bool
    original_cwd: Path
    api_provider: str
    api_base_url: str | None

    @classmethod
    def from_environment(cls, model_override: str | None = None) -> "RuntimeConfig":
        cwd = Path.cwd()
        home = Path(
            os.environ.get("FRENCH_CONFIG_HOME")
            or os.environ.get("CLAUDE_CONFIG_HOME")
            or Path.home()
        )
        from claude_code_py.services.config_store import (
            DEFAULT_SETTINGS,
            KEY_BASE_URL,
            KEY_MODEL,
            KEY_PROVIDER,
            ensure_config_dir,
            get_config_value,
        )
        # Create the settings directory and seed LM Studio defaults on first run.
        ensure_config_dir(home)
        config_model = get_config_value(KEY_MODEL, home)
        config_provider = get_config_value(KEY_PROVIDER, home) or DEFAULT_SETTINGS[KEY_PROVIDER]
        config_base_url = get_config_value(KEY_BASE_URL, home) or DEFAULT_SETTINGS[KEY_BASE_URL]
        env_model = os.environ.get("FRENCH_MODEL") or os.environ.get("ANTHROPIC_MODEL")
        env_provider = os.environ.get("FRENCH_PROVIDER") or os.environ.get("CLAUDE_API_PROVIDER")
        env_base_url = os.environ.get("FRENCH_BASE_URL") or os.environ.get("CLAUDE_API_BASE_URL")
        return cls(
            cwd=cwd,
            home=home,
            model=model_override or env_model or config_model or DEFAULT_SETTINGS[KEY_MODEL],
            is_remote=os.environ.get("CLAUDE_CODE_REMOTE") == "true",
            original_cwd=Path(os.environ.get("CLAUDE_CODE_ORIGINAL_CWD", cwd)),
            api_provider=env_provider or config_provider,
            api_base_url=env_base_url or config_base_url,
        )
