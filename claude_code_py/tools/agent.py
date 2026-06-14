from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def agent(
    description: str,
    prompt: str,
    subagent_type: str | None = None,
    model: str | None = None,
    run_in_background: bool = False,
    name: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    agent_id = str(uuid4())[:8]
    if run_in_background:
        from claude_code_py.services.config_store import project_dir
        output_dir = project_dir() / "agents"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{agent_id}.json"
        output_file.write_text(
            json.dumps(
                {
                    "status": "async_launched",
                    "agentId": agent_id,
                    "description": description,
                    "prompt": prompt,
                    "subagent_type": subagent_type,
                    "model": model,
                    "name": name,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "status": "async_launched",
            "agentId": agent_id,
            "description": description,
            "prompt": prompt,
            "outputFile": str(output_file),
            "canReadOutputFile": True,
        }

    from claude_code_py.config import RuntimeConfig
    from claude_code_py.query import run_single_turn

    config = RuntimeConfig.from_environment(model_override=model)
    result = run_single_turn(config, prompt, stream=False)
    return {"status": "completed", "result": result, "prompt": prompt}
