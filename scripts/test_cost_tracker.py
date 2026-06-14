from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_code_py.services.cost_tracker import CostTracker, canonical_model_name, format_cost, format_duration


def test_canonical_model_name():
    # New 2026 models
    assert canonical_model_name("claude-fable-5") == "claude-fable-5"
    assert canonical_model_name("Claude Fable 5") == "claude-fable-5"
    assert canonical_model_name("claude-opus-4-8") == "claude-opus-4-8"
    assert canonical_model_name("claude-opus-4-7") == "claude-opus-4-7"
    assert canonical_model_name("claude-opus-4-6") == "claude-opus-4-6"
    assert canonical_model_name("claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert canonical_model_name("claude-sonnet-4-5") == "claude-sonnet-4-5"
    assert canonical_model_name("claude-haiku-4-5") == "claude-haiku-4-5"
    # Legacy models
    assert canonical_model_name("claude-3-7-sonnet") == "claude-3-7-sonnet"
    assert canonical_model_name("claude-3-5-sonnet-20241022") == "claude-sonnet-4-6"  # default
    assert canonical_model_name("claude-3-5-haiku-20241022") == "claude-3-5-haiku"
    assert canonical_model_name("claude-3-opus-20240229") == "claude-opus-4-8"  # default opus
    # Unknown defaults to sonnet 4.6
    assert canonical_model_name("unknown-model") == "claude-sonnet-4-6"


def test_format_cost():
    assert format_cost(0.0) == "$0.00"
    assert format_cost(0.00123) == "$0.0012"
    assert format_cost(1.2345) == "$1.23"


def test_format_duration():
    assert format_duration(12.3) == "12.3s"
    assert format_duration(75) == "1m 15.0s"


def test_cost_tracker():
    tracker = CostTracker()

    # Track usage on Sonnet
    cost = tracker.add_usage(
        model="claude-3-5-sonnet",
        input_tokens=100000,      # 100k tokens at $3/M = $0.30
        output_tokens=10000,      # 10k tokens at $15/M = $0.15
        cache_read_tokens=50000,  # 50k tokens at $0.30/M = $0.015
        cache_creation_tokens=20000, # 20k tokens at $3.75/M = $0.075
        web_search_requests=2,     # 2 requests at $0.01 = $0.02
    )

    expected_cost = 0.30 + 0.15 + 0.015 + 0.075 + 0.02
    assert abs(cost - expected_cost) < 1e-6
    assert abs(tracker.total_cost_usd - expected_cost) < 1e-6

    tracker.add_api_duration(4.5)
    assert tracker.total_api_duration == 4.5

    tracker.add_lines_changed(15, 5)
    assert tracker.total_lines_added == 15
    assert tracker.total_lines_removed == 5

    summary = tracker.format_total_cost()
    assert "Total cost:            $0.56" in summary
    assert "Total duration (API):  4.5s" in summary
    assert "Total code changes:    15 lines added, 5 lines removed" in summary
    assert "claude-sonnet-4-6:" in summary


def test_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        tracker = CostTracker()
        tracker.add_usage(model="claude-3-opus", input_tokens=1000000, output_tokens=100000)
        tracker.add_lines_changed(50, 10)
        tracker.add_api_duration(15.2)

        tracker.save_to_state(home)

        # Load into another tracker
        tracker2 = CostTracker()
        tracker2.load_from_state(home)

        assert abs(tracker2.total_cost_usd - tracker.total_cost_usd) < 1e-6
        assert tracker2.total_lines_added == 50
        assert tracker2.total_lines_removed == 10
        assert tracker2.total_api_duration == 15.2
        assert "claude-opus-4-8" in tracker2.model_usage


def main():
    test_canonical_model_name()
    test_format_cost()
    test_format_duration()
    test_cost_tracker()
    test_persistence()
    print("CostTracker unit tests OK")


if __name__ == "__main__":
    main()
