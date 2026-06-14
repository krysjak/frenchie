from __future__ import annotations

from typing import Any

import httpx


def web_fetch(url: str, timeout: float = 30.0, **_: Any) -> dict[str, Any]:
    response = httpx.get(url, follow_redirects=True, timeout=timeout)
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "text": response.text,
    }


def web_search(query: str, **_: Any) -> dict[str, Any]:
    return {
        "query": query,
        "results": [],
        "message": "WebSearch requires a search provider integration; this Python port has the tool contract but no provider configured yet.",
    }
