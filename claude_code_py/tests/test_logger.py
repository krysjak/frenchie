"""Tests for the centralized logging system."""

import logging
import os
import tempfile
from pathlib import Path

from claude_code_py.logger import (
    get_logger,
    get_log_path,
    tail_log,
    rotate_log,
    resolve_log_dir,
    resolve_log_level,
    log_path_command,
    show_log_tail,
    _reset_logger,
)


class TestResolveLogDir:
    """Test log directory resolution."""

    def test_default_dir(self) -> None:
        """Default should be ~/.frenchie/logs."""
        log_dir = resolve_log_dir()
        assert ".frenchie" in str(log_dir)
        assert log_dir.name == "logs"

    def test_with_home(self) -> None:
        """With custom home, should use <home>/.frenchie/logs."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            log_dir = resolve_log_dir(home)
            assert str(home) in str(log_dir)
            assert log_dir.name == "logs"

    def test_env_override(self) -> None:
        """FRENCH_LOG_DIR env var should override default."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FRENCH_LOG_DIR"] = tmp
            try:
                log_dir = resolve_log_dir()
                assert str(log_dir) == str(Path(tmp).resolve())
            finally:
                del os.environ["FRENCH_LOG_DIR"]


class TestResolveLogLevel:
    """Test log level resolution."""

    def test_default_level(self) -> None:
        """Default level should be INFO."""
        level = resolve_log_level()
        assert level == logging.INFO

    def test_env_debug(self) -> None:
        """FRENCH_LOG_LEVEL=DEBUG should return DEBUG."""
        os.environ["FRENCH_LOG_LEVEL"] = "DEBUG"
        try:
            level = resolve_log_level()
            assert level == logging.DEBUG
        finally:
            del os.environ["FRENCH_LOG_LEVEL"]

    def test_env_error(self) -> None:
        os.environ["FRENCH_LOG_LEVEL"] = "ERROR"
        try:
            level = resolve_log_level()
            assert level == logging.ERROR
        finally:
            del os.environ["FRENCH_LOG_LEVEL"]

    def test_env_invalid(self) -> None:
        """Invalid env value should default to INFO."""
        os.environ["FRENCH_LOG_LEVEL"] = "INVALID"
        try:
            level = resolve_log_level()
            assert level == logging.INFO
        finally:
            del os.environ["FRENCH_LOG_LEVEL"]


class TestGetLogger:
    """Test the logger singleton."""

    def test_root_logger(self) -> None:
        _reset_logger()
        logger = get_logger()
        assert logger.name == "frenchie"
        assert logger.level == resolve_log_level()

    def test_sub_logger(self) -> None:
        _reset_logger()
        sub = get_logger("test-module")
        assert sub.name == "frenchie.test-module"

    def test_singleton(self) -> None:
        _reset_logger()
        l1 = get_logger()
        l2 = get_logger()
        assert l1 is l2

    def test_logger_writes_to_file(self) -> None:
        """After getting a logger, a log file should exist."""
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                logger = get_logger(home=home)
                logger.info("Test message")
                log_path = get_log_path(home)
                assert log_path.exists()
                content = log_path.read_text(encoding="utf-8")
                assert "Test message" in content
                assert "INFO" in content
            finally:
                _reset_logger()

    def test_logger_levels(self) -> None:
        """Different log levels should be written correctly."""
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                logger = get_logger(home=home)
                logger.debug("Debug msg")
                logger.info("Info msg")
                logger.warning("Warning msg")
                logger.error("Error msg")
                content = get_log_path(home).read_text(encoding="utf-8")
                assert "INFO" in content
                assert "WARNING" in content
                assert "ERROR" in content
                # DEBUG should NOT appear at default level (INFO)
                assert "Debug msg" not in content
            finally:
                _reset_logger()

    def test_sub_logger_name_in_output(self) -> None:
        """Sub-logger name should appear in log output."""
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                sub = get_logger("mymodule", home=home)
                sub.info("Hello from module")
                content = get_log_path(home).read_text(encoding="utf-8")
                assert "mymodule" in content
                assert "Hello from module" in content
            finally:
                _reset_logger()


class TestTailLog:
    """Test the tail_log function."""

    def test_nonexistent_file(self) -> None:
        """Non-existent log file should return empty string."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = tail_log(home, n_lines=10)
            assert result == ""

    def test_tail_content(self) -> None:
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                logger = get_logger(home=home)
                for i in range(20):
                    logger.info("Line %d", i)
                result = tail_log(home, n_lines=5)
                lines = result.splitlines()
                assert len(lines) == 5
                assert "Line 19" in lines[-1]
            finally:
                _reset_logger()

    def test_tail_all(self) -> None:
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                logger = get_logger(home=home)
                for i in range(10):
                    logger.info("Entry %d", i)
                result = tail_log(home, n_lines=100)
                lines = result.splitlines()
                # 1 init line + 10 entries = 11 total
                assert len(lines) == 11
            finally:
                _reset_logger()


class TestRotateLog:
    """Test manual log rotation."""

    def test_nonexistent_rotate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            assert rotate_log(home) is False

    def test_rotate_creates_backup(self) -> None:
        _reset_logger()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                home = Path(tmp)
                logger = get_logger(home=home)
                logger.info("Before rotation")
                assert rotate_log(home) is True
                # Backup should exist
                backup = get_log_path(home).with_suffix(".log.1")
                assert backup.exists()
                assert "Before rotation" in backup.read_text(encoding="utf-8")
            finally:
                _reset_logger()


class TestLogHelpers:
    """Test logging helper functions (non-interactive parts)."""

    def test_get_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = get_log_path(home)
            assert str(path).endswith("frenchie.log")

    def test_log_path_command_output(self) -> None:
        """log_path_command should not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            log_path_command(home)  # Should not raise

    def test_show_log_tail_empty(self) -> None:
        """show_log_tail with no log file should not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            show_log_tail(home)  # Should not raise
