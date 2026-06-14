from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def glob_files(pattern: str, path: str | None = None, **_: Any) -> dict[str, Any]:
    root = Path(path).expanduser() if path else Path.cwd()
    if not root.is_absolute():
        root = root.resolve()
    matches = [p for p in root.glob(pattern) if p.exists()]
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return {"root": str(root), "matches": [str(p) for p in matches]}


def grep(
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    output_mode: str = "files_with_matches",
    multiline: bool = False,
    case_insensitive: bool = False,
    **_: Any,
) -> dict[str, Any]:
    root = Path(path).expanduser() if path else Path.cwd()
    if not root.is_absolute():
        root = root.resolve()
    rg = shutil.which("rg")
    if rg:
        rg_mode = "--line-number" if output_mode == "content" else "--files-with-matches"
        args = [rg, rg_mode, pattern, str(root)]
        if case_insensitive:
            args.insert(1, "-i")
        if multiline:
            args.insert(1, "-U")
        if glob:
            args[1:1] = ["-g", glob]
        if output_mode == "count":
            args = [rg, "--count", pattern, str(root)]
            if case_insensitive:
                args.insert(1, "-i")
            if glob:
                args[1:1] = ["-g", glob]
        completed = subprocess.run(args, text=True, capture_output=True, check=False)
        if completed.returncode not in (0, 1):
            raise RuntimeError(completed.stderr.strip())
        return {"root": str(root), "output_mode": output_mode, "output": completed.stdout.strip()}

    flags = re.IGNORECASE if case_insensitive else 0
    flags |= re.DOTALL if multiline else 0
    regex = re.compile(pattern, flags)
    results: dict[str, Any] = {} if output_mode == "count" else {"matches": []}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if glob and not fnmatch.fnmatch(str(file_path.relative_to(root)), glob):
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        found = list(regex.finditer(text))
        if not found:
            continue
        if output_mode == "files_with_matches":
            results["matches"].append(str(file_path))
        elif output_mode == "count":
            results[str(file_path)] = len(found)
        else:
            lines = text.splitlines()
            for number, line in enumerate(lines, start=1):
                if regex.search(line):
                    results["matches"].append({"file": str(file_path), "line": number, "content": line})
    return {"root": str(root), "output_mode": output_mode, "output": results}
