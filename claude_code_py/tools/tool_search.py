from __future__ import annotations

import re
from typing import Any


def _parts(name: str) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").lower()


def tool_search(query: str, max_results: int = 5) -> dict[str, Any]:
    from claude_code_py.tools import tool_registry

    query_lower = query.lower().strip()
    names = tool_registry.names()
    if query_lower.startswith("select:"):
        selected = query_lower.removeprefix("select:").strip()
        matches = [name for name in names if name.lower() == selected]
    else:
        terms = [term for term in query_lower.split() if term]
        scored: list[tuple[int, str]] = []
        for name in names:
            tool = tool_registry.get(name)
            haystack = f"{_parts(name)} {tool.description.lower()}"
            score = sum(3 if term in name.lower() else 1 for term in terms if term in haystack)
            if not terms or score:
                scored.append((score, name))
        matches = [name for _, name in sorted(scored, key=lambda item: (-item[0], item[1]))[:max_results]]
    return {"matches": matches, "query": query, "total_deferred_tools": len(names)}
