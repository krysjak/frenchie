from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from claude_code_py.services.state_store import StateStore

MODEL_PRICING = {
    # Claude Fable 5 (Mythos-class, 2026)
    "claude-fable-5": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "search": 0.01,
    },
    # Claude Opus 4.8 (current top model, 2026)
    "claude-opus-4-8": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "search": 0.01,
    },
    # Claude Opus 4.7
    "claude-opus-4-7": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "search": 0.01,
    },
    # Claude Opus 4.6
    "claude-opus-4-6": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "search": 0.01,
    },
    # Claude Sonnet 4.6 (default, 2026)
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
        "search": 0.01,
    },
    # Claude Sonnet 4.5
    "claude-sonnet-4-5": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
        "search": 0.01,
    },
    # Claude 3.7 Sonnet
    "claude-3-7-sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
        "search": 0.01,
    },
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
        "search": 0.01,
    },
    # Claude 3.5 Haiku
    "claude-3-5-haiku": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00,
        "search": 0.01,
    },
    # Claude Haiku 4.5
    "claude-haiku-4-5": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00,
        "search": 0.01,
    },
    # Claude 3 Opus (legacy)
    "claude-3-opus": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "search": 0.01,
    },
}

DEFAULT_TIER = MODEL_PRICING["claude-sonnet-4-6"]


def canonical_model_name(model: str) -> str:
    m = model.lower().replace("[1m]", "").replace("[1M]", "").strip()
    # Fable 5
    if "fable" in m and "5" in m:
        return "claude-fable-5"
    # Opus series
    if "opus" in m:
        if "4-8" in m or "4.8" in m:
            return "claude-opus-4-8"
        if "4-7" in m or "4.7" in m:
            return "claude-opus-4-7"
        if "4-6" in m or "4.6" in m:
            return "claude-opus-4-6"
        return "claude-opus-4-8"  # default opus
    # Haiku series
    if "haiku" in m:
        if "4-5" in m or "4.5" in m:
            return "claude-haiku-4-5"
        return "claude-3-5-haiku"
    # Sonnet series
    if "sonnet" in m:
        if "4-6" in m or "4.6" in m:
            return "claude-sonnet-4-6"
        if "4-5" in m or "4.5" in m:
            return "claude-sonnet-4-5"
        if "3-7" in m or "3.7" in m:
            return "claude-3-7-sonnet"
        return "claude-sonnet-4-6"  # default sonnet
    # Fallback
    return "claude-sonnet-4-6"


def format_cost(amount: float) -> str:
    if amount == 0:
        return "$0.00"
    if amount > 0.5:
        return f"${amount:.2f}"
    return f"${amount:.4f}"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = seconds % 60
    return f"{minutes}m {remaining:.1f}s"


def format_number(val: int) -> str:
    return f"{val:,}"


class CostTracker:
    def __init__(self) -> None:
        self.wall_start_time = time.time()
        self.reset()

    def reset(self) -> None:
        self.total_cost_usd = 0.0
        self.total_api_duration = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cache_creation_tokens = 0
        self.total_lines_added = 0
        self.total_lines_removed = 0
        self.model_usage: dict[str, dict[str, Any]] = {}
        self.web_search_requests = 0

    def load_from_state(self, home_dir: Path) -> None:
        try:
            from claude_code_py.services.config_store import config_dir
            state = StateStore(config_dir(home_dir)).load()
            cost_data = state.get("cost_data", {})
            if cost_data:
                self.total_cost_usd = cost_data.get("total_cost_usd", 0.0)
                self.total_api_duration = cost_data.get("total_api_duration", 0.0)
                self.total_input_tokens = cost_data.get("total_input_tokens", 0)
                self.total_output_tokens = cost_data.get("total_output_tokens", 0)
                self.total_cache_read_tokens = cost_data.get("total_cache_read_tokens", 0)
                self.total_cache_creation_tokens = cost_data.get("total_cache_creation_tokens", 0)
                self.total_lines_added = cost_data.get("total_lines_added", 0)
                self.total_lines_removed = cost_data.get("total_lines_removed", 0)
                self.model_usage = cost_data.get("model_usage", {})
                self.web_search_requests = cost_data.get("web_search_requests", 0)
        except Exception:
            pass

    def save_to_state(self, home_dir: Path) -> None:
        try:
            from claude_code_py.services.config_store import config_dir
            store = StateStore(config_dir(home_dir))
            cost_data = {
                "total_cost_usd": self.total_cost_usd,
                "total_api_duration": self.total_api_duration,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cache_read_tokens": self.total_cache_read_tokens,
                "total_cache_creation_tokens": self.total_cache_creation_tokens,
                "total_lines_added": self.total_lines_added,
                "total_lines_removed": self.total_lines_removed,
                "model_usage": self.model_usage,
                "web_search_requests": self.web_search_requests,
            }
            store.set("cost_data", cost_data)
        except Exception:
            pass

    def add_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        web_search_requests: int = 0,
    ) -> float:
        canonical = canonical_model_name(model)
        tier = MODEL_PRICING.get(canonical, DEFAULT_TIER)

        # Calculate cost
        cost = (
            (input_tokens / 1_000_000.0) * tier["input"]
            + (output_tokens / 1_000_000.0) * tier["output"]
            + (cache_read_tokens / 1_000_000.0) * tier["cache_read"]
            + (cache_creation_tokens / 1_000_000.0) * tier["cache_write"]
            + web_search_requests * tier["search"]
        )

        self.total_cost_usd += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cache_read_tokens += cache_read_tokens
        self.total_cache_creation_tokens += cache_creation_tokens
        self.web_search_requests += web_search_requests

        if canonical not in self.model_usage:
            self.model_usage[canonical] = {
                "input": 0,
                "output": 0,
                "cache_read": 0,
                "cache_write": 0,
                "search": 0,
                "cost": 0.0,
            }

        usage = self.model_usage[canonical]
        usage["input"] += input_tokens
        usage["output"] += output_tokens
        usage["cache_read"] += cache_read_tokens
        usage["cache_write"] += cache_creation_tokens
        usage["search"] += web_search_requests
        usage["cost"] += cost

        return cost

    def add_api_duration(self, seconds: float) -> None:
        self.total_api_duration += seconds

    def add_lines_changed(self, added: int, removed: int) -> None:
        self.total_lines_added += added
        self.total_lines_removed += removed

    def format_total_cost(self) -> str:
        cost_str = format_cost(self.total_cost_usd)
        api_dur = format_duration(self.total_api_duration)
        wall_dur = format_duration(time.time() - self.wall_start_time)
        added_label = "line" if self.total_lines_added == 1 else "lines"
        removed_label = "line" if self.total_lines_removed == 1 else "lines"

        lines = [
            f"Total cost:            {cost_str}",
            f"Total duration (API):  {api_dur}",
            f"Total duration (wall): {wall_dur}",
            f"Total code changes:    {self.total_lines_added} {added_label} added, {self.total_lines_removed} {removed_label} removed",
        ]

        if not self.model_usage:
            lines.append("Usage:                 0 input, 0 output, 0 cache read, 0 cache write")
        else:
            lines.append("Usage by model:")
            for model_name, usage in sorted(self.model_usage.items()):
                model_str = f"{model_name}:"
                search_part = f", {usage['search']} web search" if usage["search"] > 0 else ""
                usage_line = (
                    f"  {format_number(usage['input'])} input, "
                    f"{format_number(usage['output'])} output, "
                    f"{format_number(usage['cache_read'])} cache read, "
                    f"{format_number(usage['cache_write'])} cache write"
                    f"{search_part} ({format_cost(usage['cost'])})"
                )
                lines.append(f"{model_str:>22}{usage_line}")

        return "\n".join(lines)


# Global singleton instance
cost_tracker = CostTracker()
