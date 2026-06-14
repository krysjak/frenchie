"""Central logging system for Frenchie.

Provides:
- Rotating file logs (configurable dir, size, backup count)
- Multiple log levels: DEBUG, INFO, WARNING, ERROR
- Structured output with timestamps, levels, and module names
- A convenience /logs CLI command
- Environment variable override (FRENCH_LOG_LEVEL, FRENCH_LOG_DIR)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ── Log Format ───────────────────────────────────────────────────────────────
_LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_DEFAULT_BACKUP_COUNT = 3
_DEFAULT_LEVEL: LogLevel = "INFO"


def resolve_log_dir(home: Path | None = None) -> Path:
    """Determine the log directory (default: ~/.frenchie/logs)."""
    override = os.environ.get("FRENCH_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    from claude_code_py.services.config_store import config_dir
    return config_dir(home) / "logs"


def resolve_log_level() -> int:
    """Resolve the log level from env or default."""
    env = (os.environ.get("FRENCH_LOG_LEVEL") or "INFO").upper()
    return _LOG_LEVELS.get(env, logging.INFO)


# ── Logger singleton ─────────────────────────────────────────────────────────
_logger: logging.Logger | None = None


def _close_handlers(logger: logging.Logger) -> None:
    """Close all handlers on *logger* and then clear them.

    On Windows, closing is required because the file handle prevents
    the underlying log file from being deleted or renamed while the
    process holds it open.
    """
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def _reset_logger() -> None:
    """Reset the logger singleton (used primarily in tests)."""
    global _logger
    if _logger is not None:
        _close_handlers(_logger)
    _logger = None


def get_logger(
    name: str | None = None,
    level: LogLevel | None = None,
    home: Path | None = None,
) -> logging.Logger:
    """Get or create the root Frenchie logger.

    The logger writes to both a rotating file (in ~/.frenchie/logs/) and
    stderr (only when FRENCH_LOG_STDERR=1 is set).

    The logger is a singleton: the first call determines the log file
    location. Subsequent calls with a different *home* are ignored
    unless *_reset_logger()* is called first.

    Args:
        name: Sub-logger name (e.g. "repl", "mcp"). If None, returns root logger.
        level: Override log level.
        home: Override home directory for log file location (first call only).

    Returns:
        A Python ``logging.Logger`` instance.
    """
    global _logger

    if _logger is None:
        _logger = logging.getLogger("frenchie")
        _logger.setLevel(resolve_log_level())
        _logger.handlers.clear()

        # ── File handler with rotation ──
        log_dir = resolve_log_dir(home)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "frenchie.log"

        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=_DEFAULT_MAX_BYTES,
            backupCount=_DEFAULT_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File captures everything
        file_formatter = logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        _logger.addHandler(file_handler)

        # ── Stderr handler (opt-in via env) ──
        if os.environ.get("FRENCH_LOG_STDERR") == "1":
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setLevel(resolve_log_level())
            stderr_formatter = logging.Formatter(
                "[%(levelname)s] %(name)s: %(message)s",
            )
            stderr_handler.setFormatter(stderr_formatter)
            _logger.addHandler(stderr_handler)

        _logger.info(
            "Logger initialised — file: %s, level: %s",
            log_path,
            logging.getLevelName(_logger.level),
        )

    if level:
        effective_level = _LOG_LEVELS.get(level.upper(), logging.INFO)
        _logger.setLevel(effective_level)
        for handler in _logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(effective_level)

    if name:
        return logging.getLogger(f"frenchie.{name}")
    return _logger


# ── Convenience functions ────────────────────────────────────────────────────
def get_log_path(home: Path | None = None) -> Path:
    """Return the path to the current log file."""
    return resolve_log_dir(home) / "frenchie.log"


def tail_log(
    home: Path | None = None,
    n_lines: int = 50,
) -> str:
    """Return the last *n_lines* of the log file as a string.

    Returns an empty string if the log file does not exist.
    """
    log_path = get_log_path(home)
    if not log_path.exists():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-n_lines:])
    except Exception:
        return ""


def rotate_log(home: Path | None = None) -> bool:
    """Force a log rotation. Returns True on success."""
    global _logger
    log_path = get_log_path(home)
    if not log_path.exists():
        return False
    # Close the current file handler so the file can be renamed
    # on platforms (Windows) that lock open files.
    if _logger is not None:
        _close_handlers(_logger)

    try:
        backup = log_path.with_suffix(".log.1")
        if backup.exists():
            backup.unlink()
        log_path.rename(backup)
    except Exception as exc:
        logging.getLogger("frenchie").error("rotate_log rename failed: %s", exc)
        return False

    # Re-initialise handlers by calling get_logger again.
    _logger = None
    try:
        logger = get_logger(home=home)
        logger.info("Log rotated — previous log moved to %s", backup)
        return True
    except Exception as exc:
        logging.getLogger("frenchie").error("rotate_log reinit failed: %s", exc)
        return False


def log_path_command(home: Path) -> None:
    """Print the log file path (used by the /logs CLI command)."""
    from rich.console import Console
    console = Console()
    log_path = get_log_path(home)
    if log_path.exists():
        size = log_path.stat().st_size
        from claude_code_py.services.cost_tracker import format_number
        console.print(f"  [dim]Log file:[/dim] [bold]{log_path}[/bold]")
        console.print(f"  [dim]Size:[/dim] {format_number(size)} bytes")
    else:
        console.print(f"  [dim]Log file:[/dim] [bold]{log_path}[/bold] [dim](not yet created)[/dim]")


def show_log_tail(home: Path, n: int = 50) -> None:
    """Print the last *n* lines of the log file to the console."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    console = Console()
    content = tail_log(home, n_lines=n)
    if not content:
        console.print("  [dim]No log entries yet.[/dim]")
        return
    syntax = Syntax(content, "text", theme="monokai", line_numbers=True)
    console.print(Panel(
        syntax,
        title="[bold #e5484d]Recent Logs[/bold #e5484d]",
        border_style="#e5484d",
        expand=False,
    ))
