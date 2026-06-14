from __future__ import annotations

import re


DESTRUCTIVE_SHELL_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bRemove-Item\b.*\s-Recurse\b",
    r"\bdel\s+/[sq]\b",
    r"\bformat\b",
    r"\bdd\s+if=",
]


def has_destructive_pattern(command: str) -> str | None:
    for pattern in DESTRUCTIVE_SHELL_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def detect_blocked_sleep(command: str) -> str | None:
    first = re.split(r"[;|&\r\n]", command.strip(), maxsplit=1)[0].strip()
    match = re.match(r"^(?:sleep|start-sleep)(?:\s+-s(?:econds)?)?\s+(\d+)\s*$", first, re.IGNORECASE)
    if not match:
        return None
    seconds = int(match.group(1))
    if seconds < 2:
        return None
    return f"standalone sleep {seconds}"


def validate_shell_command(command: str, allow_destructive: bool = False) -> None:
    sleep = detect_blocked_sleep(command)
    if sleep:
        raise ValueError(f"Blocked long foreground sleep: {sleep}")
    destructive = has_destructive_pattern(command)
    if destructive and not allow_destructive:
        raise ValueError(f"Potentially destructive command requires explicit override: {destructive}")
