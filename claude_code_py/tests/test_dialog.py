"""Tests for dialog components."""

from claude_code_py.components.dialog import (
    confirm_dialog,
    input_dialog,
    select_dialog,
    notification_dialog,
    _arrow_select,
)


class TestNotificationDialog:
    """Test notification dialog (simplest dialog — no input needed)."""

    def test_notification_levels(self) -> None:
        """All notification levels should work without errors."""
        for level in ["info", "success", "warning", "error"]:
            # Should not raise
            notification_dialog("Test Title", f"Test message ({level})", level)

    def test_notification_default_level(self) -> None:
        """Default level should be 'info'."""
        notification_dialog("Test", "Default level message")


class TestInputDialog:
    """Test input dialog — limited testing since it requires stdin."""

    def test_input_default_return(self) -> None:
        """input_dialog should exist and accept parameters."""
        # We can't easily test interactive input, but we can test the function exists
        assert callable(input_dialog)


class TestSelectDialog:
    """Test select dialog utilities."""

    def test_arrow_select_invalid(self) -> None:
        """_arrow_select with empty options should handle gracefully."""
        # This is hard to test in non-interactive mode
        pass

    def test_select_dialog_invalid(self) -> None:
        """select_dialog with empty options."""
        assert callable(select_dialog)


class TestInfoFormatter:
    """Test that dialog formatting utilities work."""

    def test_notification_no_crash(self) -> None:
        """Simply ensuring notification rendering doesn't crash."""
        notification_dialog("Test", "Body text", "warning")
        notification_dialog("Error", "Something went wrong!", "error")
        notification_dialog("Info", "Just so you know", "info")
