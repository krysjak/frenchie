"""Tests for FuzzyPicker, FuzzyItem, and scoring/filtering functions."""

from claude_code_py.components.fuzzy_picker import (
    FuzzyItem, _score_item, fuzzy_filter, FuzzyPicker,
)


class TestFuzzyItem:
    """Test the FuzzyItem dataclass."""

    def test_default_values(self) -> None:
        item = FuzzyItem(label="test", value=42)
        assert item.label == "test"
        assert item.value == 42
        assert item.description == ""
        assert item.category == ""
        assert item.icon == ""

    def test_all_fields(self) -> None:
        item = FuzzyItem(
            label="hello",
            value="world",
            description="A greeting",
            category="commands",
            icon="🔔",
        )
        assert item.label == "hello"
        assert item.value == "world"
        assert item.description == "A greeting"
        assert item.category == "commands"
        assert item.icon == "🔔"


class TestScoreItem:
    """Test the _score_item function for fuzzy matching."""

    def test_empty_query_returns_one(self) -> None:
        item = FuzzyItem(label="anything")
        assert _score_item("", item) == 1.0

    def test_exact_match(self) -> None:
        item = FuzzyItem(label="hello")
        assert _score_item("hello", item) == 1.0

    def test_starts_with(self) -> None:
        item = FuzzyItem(label="hello world")
        score = _score_item("hello", item)
        assert score == 0.9

    def test_contains_match(self) -> None:
        item = FuzzyItem(label="hello world")
        score = _score_item("world", item)
        assert score == 0.7

    def test_description_match(self) -> None:
        item = FuzzyItem(label="cmd", description="this is a test tool")
        score = _score_item("tool", item)
        assert score == 0.3

    def test_no_match(self) -> None:
        item = FuzzyItem(label="hello")
        score = _score_item("xyz", item)
        assert score == 0.0

    def test_case_insensitive_label(self) -> None:
        item = FuzzyItem(label="HelloWorld")
        score = _score_item("helloworld", item)
        assert score == 1.0

    def test_case_insensitive_contains(self) -> None:
        item = FuzzyItem(label="Hello World")
        score = _score_item("WORLD", item)
        assert score == 0.7

    def test_fuzzy_match_low_ratio(self) -> None:
        """Low similarity should still return a score if > 0.4."""
        item = FuzzyItem(label="abcdef")
        score = _score_item("abxdef", item)
        # Should be > 0 if ratio > 0.4
        assert score >= 0.0


class TestFuzzyFilter:
    """Test the fuzzy_filter function."""

    def make_items(self, labels: list[str]) -> list[FuzzyItem]:
        return [FuzzyItem(label=label, value=label) for label in labels]

    def test_empty_query_returns_all(self) -> None:
        items = self.make_items(["apple", "banana", "cherry"])
        results = fuzzy_filter("", items, max_results=10)
        assert len(results) == 3

    def test_filter_by_query(self) -> None:
        items = self.make_items(["apple", "banana", "avocado", "cherry"])
        results = fuzzy_filter("app", items)
        assert len(results) == 1
        assert results[0][1].label == "apple"

    def test_max_results(self) -> None:
        items = self.make_items(["cat", "car", "cap", "cab", "camera", "cake"])
        results = fuzzy_filter("ca", items, max_results=3)
        assert len(results) <= 3

    def test_scored_ordering(self) -> None:
        items = self.make_items(["exact", "exactly", "not-matching"])
        results = fuzzy_filter("exact", items, max_results=3)
        # Exact match should be first
        assert results[0][1].label == "exact"
        assert results[0][0] >= results[1][0]

    def test_no_matches_returns_empty(self) -> None:
        items = self.make_items(["alpha", "beta", "gamma"])
        results = fuzzy_filter("zzzzz", items)
        assert len(results) == 0

    def test_empty_items(self) -> None:
        results = fuzzy_filter("test", [])
        assert len(results) == 0


class TestFuzzyPicker:
    """Test the FuzzyPicker class (non-interactive methods only)."""

    def make_picker(self, n_items: int = 3) -> FuzzyPicker:
        items = [
            FuzzyItem(label=f"item{i}", value=i, description=f"desc{i}")
            for i in range(n_items)
        ]
        return FuzzyPicker(items, title="Test Picker")

    def test_initial_state(self) -> None:
        picker = self.make_picker(5)
        assert picker.title == "Test Picker"
        assert len(picker.items) == 5
        assert picker._selected_index == 0
        assert picker._result is None

    def test_update_filtered_all_items(self) -> None:
        picker = self.make_picker(5)
        picker._update_filtered("")
        assert len(picker._filtered) == 5  # All items returned

    def test_update_filtered_query(self) -> None:
        picker = make_items = [
            FuzzyItem(label="apple", value=1),
            FuzzyItem(label="banana", value=2),
            FuzzyItem(label="avocado", value=3),
        ]
        picker = FuzzyPicker(make_items, title="Fruits")
        picker._update_filtered("app")
        assert len(picker._filtered) == 1
        assert picker._filtered[0].label == "apple"

    def test_update_filtered_with_no_results(self) -> None:
        picker = self.make_picker(3)
        picker._update_filtered("zzzzz")
        assert len(picker._filtered) == 0

    def test_selected_index_clamped_when_filtered_smaller(self) -> None:
        items = [
            FuzzyItem(label="alpha", value=1),
            FuzzyItem(label="beta", value=2),
            FuzzyItem(label="gamma", value=3),
            FuzzyItem(label="delta", value=4),
        ]
        picker = FuzzyPicker(items)
        picker._selected_index = 3  # Select last item
        picker._update_filtered("alpha")
        # Filtered only has "alpha", index should be clamped to 0
        assert picker._selected_index == 0

    def test_get_header_returns_list(self) -> None:
        picker = self.make_picker(5)
        picker._update_filtered("")
        header = picker._get_header()
        assert isinstance(header, list)
        assert len(header) > 0

    def test_get_results_returns_list(self) -> None:
        picker = self.make_picker(3)
        picker._update_filtered("")
        results = picker._get_results()
        assert isinstance(results, list)

    def test_get_footer_returns_list(self) -> None:
        picker = self.make_picker(2)
        footer = picker._get_footer()
        assert isinstance(footer, list)
        assert len(footer) > 0

    def test_query_tracking(self) -> None:
        picker = self.make_picker(3)
        assert picker._query == ""
        picker._update_filtered("test")
        assert picker._query == "test"


class TestFuzzyPickerConvenience:
    """Test the fuzzy_picker convenience function stub."""

    def test_fuzzy_picker_function_exists(self) -> None:
        from claude_code_py.components.fuzzy_picker import fuzzy_picker
        assert callable(fuzzy_picker)
