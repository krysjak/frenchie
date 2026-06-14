"""Tests for ProgressBar and Spinner components."""

import time
from claude_code_py.components.progress import (
    ProgressBar, Spinner, spinner_context, make_progress,
)


class TestProgressBar:
    """Test the ProgressBar component."""

    def test_initial_state(self) -> None:
        bar = ProgressBar(total=100, label="Test")
        assert bar.total == 100
        assert bar.current == 0.0
        assert bar.label == "Test"

    def test_advance(self) -> None:
        bar = ProgressBar(total=100)
        bar.advance(25)
        assert bar.current == 25
        bar.advance(50)
        assert bar.current == 75

    def test_advance_caps_at_total(self) -> None:
        bar = ProgressBar(total=100)
        bar.advance(150)
        assert bar.current == 100  # Capped

    def test_set_completed(self) -> None:
        bar = ProgressBar(total=50)
        bar.set_completed(25)
        assert bar.current == 25
        bar.set_completed(100)
        assert bar.current == 50  # Capped at total

    def test_complete_resets_to_total(self) -> None:
        bar = ProgressBar(total=100)
        bar.set_completed(50)
        bar.complete()
        assert bar.current == 100

    def test_zero_total(self) -> None:
        """ProgressBar with total=0 should not crash."""
        bar = ProgressBar(total=0)
        bar.advance(5)
        assert bar.current == 0  # Stays at 0 since total is 0

    def test_render_no_crash(self) -> None:
        """Ensure _render does not crash."""
        bar = ProgressBar(total=100)
        bar.set_completed(50)
        bar._render()  # Should not raise

    def test_complete_with_message(self) -> None:
        bar = ProgressBar(total=10, label="Task")
        bar.complete("Done!")
        assert bar.current == bar.total


class TestSpinner:
    """Test the Spinner component."""

    def test_initial_state(self) -> None:
        spinner = Spinner("Loading...")
        assert spinner.message == "Loading..."
        assert len(spinner.frames) > 0
        assert not spinner._running

    def test_start_stop(self) -> None:
        spinner = Spinner()
        spinner.start("Working")
        assert spinner._running
        assert spinner.message == "Working"
        spinner.stop()
        assert not spinner._running

    def test_update_changes_message(self) -> None:
        spinner = Spinner("Initial")
        spinner.start()
        spinner.update("Updated")
        assert spinner.message == "Updated"

    def test_render_returns_string(self) -> None:
        spinner = Spinner("Test")
        spinner.start()
        result = spinner.render()
        assert isinstance(result, str)
        assert "Test" in result
        spinner.stop()

    def test_frame_advances(self) -> None:
        spinner = Spinner()
        spinner.start()
        frame1 = spinner._frame_index
        spinner.update()
        frame2 = spinner._frame_index
        assert frame2 != frame1  # Frame index should change
        spinner.stop()

    def test_dots_spinner_works(self) -> None:
        from claude_code_py.components.progress import DOTS_SPINNER
        assert len(DOTS_SPINNER) > 0


class TestSpinnerContext:
    """Test spinner_context context manager."""

    def test_context_manager(self) -> None:
        """Context manager should run without error."""
        with spinner_context("Testing"):
            pass  # Context should work

    def test_context_yields_spinner(self) -> None:
        with spinner_context() as spinner:
            assert isinstance(spinner, Spinner)


class TestMakeProgress:
    """Test make_progress factory function."""

    def test_make_progress_defaults(self) -> None:
        progress = make_progress("Test task")
        assert progress is not None

    def test_make_progress_transient(self) -> None:
        progress = make_progress(transient=True)
        assert progress is not None
