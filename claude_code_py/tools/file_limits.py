from __future__ import annotations

import os
from pathlib import Path


MAX_OUTPUT_SIZE = int(0.25 * 1024 * 1024)
BINARY_CHECK_SIZE = 8192

BINARY_EXTENSIONS = {
    ".bmp",
    ".ico",
    ".tiff",
    ".tif",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".flv",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
    ".wma",
    ".aiff",
    ".opus",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".xz",
    ".z",
    ".tgz",
    ".iso",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".o",
    ".a",
    ".obj",
    ".lib",
    ".app",
    ".msi",
    ".deb",
    ".rpm",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".pyc",
    ".pyo",
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".node",
    ".wasm",
    ".rlib",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".mdb",
    ".idx",
    ".psd",
    ".ai",
    ".eps",
    ".sketch",
    ".fig",
    ".xd",
    ".blend",
    ".3ds",
    ".max",
    ".swf",
    ".fla",
    ".lockb",
    ".dat",
    ".data",
}


def max_output_size() -> int:
    raw = os.environ.get("CLAUDE_CODE_FILE_READ_MAX_SIZE_BYTES")
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            return MAX_OUTPUT_SIZE
        if parsed > 0:
            return parsed
    return MAX_OUTPUT_SIZE


def has_binary_extension(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def is_binary_content(data: bytes) -> bool:
    check = data[:BINARY_CHECK_SIZE]
    if not check:
        return False
    if b"\x00" in check:
        return True
    non_printable = 0
    for byte in check:
        if byte < 32 and byte not in {9, 10, 13}:
            non_printable += 1
    return non_printable / len(check) > 0.1


def assert_text_read_allowed(path: Path) -> None:
    if has_binary_extension(path):
        raise ValueError(
            f"This tool cannot read binary files. The file appears to be a binary {path.suffix.lower()} file. "
            "Please use appropriate tools for binary file analysis."
        )
    size = path.stat().st_size
    limit = max_output_size()
    if size > limit:
        raise ValueError(
            f"File content ({size} bytes) exceeds maximum allowed size ({limit} bytes). "
            "Use offset and limit parameters to read specific portions of the file, or search for specific content instead."
        )
    sample = path.read_bytes()[:BINARY_CHECK_SIZE]
    if is_binary_content(sample):
        raise ValueError("This tool cannot read binary files. The file appears to contain binary data.")
