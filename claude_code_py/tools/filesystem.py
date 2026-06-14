from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_code_py.services.read_state import ReadStateStore, assert_read_before_write, file_mtime, update_after_write
from claude_code_py.tools.file_limits import assert_text_read_allowed
from claude_code_py.tools.image_processor import MEDIA_TYPES, build_image_read_result, detect_media_type
from claude_code_py.tools.notebook import notebook_cells_to_tool_result, read_notebook
from claude_code_py.tools.pdf import build_pdf_read_result


MAX_LINES_TO_READ = 2000
FILE_UNCHANGED_STUB = "File unchanged since last read. The content from the earlier Read tool_result in this conversation is still current; refer to that instead of re-reading."


def _path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("file_path must be an absolute path")
    return path


def read_file(file_path: str, offset: int = 1, limit: int | None = None, **_: Any) -> dict[str, Any]:
    path = _path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.is_dir():
        raise IsADirectoryError(str(path))
    start = max(offset, 1) - 1
    count = limit if limit is not None else MAX_LINES_TO_READ
    read_state = ReadStateStore().get(path)
    if read_state and file_mtime(path) <= read_state.timestamp and read_state.offset == start + 1 and read_state.limit == count:
        return {
            "file_path": str(path),
            "line_count": None,
            "offset": start + 1,
            "limit": count,
            "content": FILE_UNCHANGED_STUB,
        }
    if path.suffix.lower() in MEDIA_TYPES:
        data = path.read_bytes()
        if detect_media_type(path, data):
            result = build_image_read_result(path, data)
            result.update({"offset": start + 1, "limit": count, "line_count": None})
            ReadStateStore().set(path, result["content"], offset=start + 1, limit=count)
            return result
    if path.suffix.lower() == ".pdf":
        result = build_pdf_read_result(path, pages=_.get("pages"))
        result.update({"offset": start + 1, "limit": count, "line_count": None})
        ReadStateStore().set(path, result["content"], offset=start + 1, limit=count)
        return result
    if path.suffix.lower() == ".ipynb":
        notebook = read_notebook(str(path), cell_id=_.get("cell_id"))
        content = "\n".join(block["text"] for block in notebook_cells_to_tool_result(notebook) if block["type"] == "text")
        ReadStateStore().set(path, content, offset=start + 1, limit=count)
        return {
            **notebook,
            "line_count": None,
            "offset": start + 1,
            "limit": count,
            "content": content,
            "_tool_result_content": notebook_cells_to_tool_result(notebook),
        }
    assert_text_read_allowed(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start : start + count]
    numbered = [f"{index + start + 1:>6}\t{line}" for index, line in enumerate(selected)]
    content = "\n".join(numbered)
    ReadStateStore().set(path, "\n".join(lines), offset=start + 1, limit=count)
    return {
        "file_path": str(path),
        "line_count": len(lines),
        "offset": start + 1,
        "limit": count,
        "content": content,
    }


def write_file(file_path: str, content: str, **_: Any) -> dict[str, Any]:
    path = _path(file_path)
    assert_read_before_write(path)
    original_lines = 0
    if path.exists():
        try:
            original_lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    update_after_write(path, content)
    new_lines = len(content.splitlines())
    from claude_code_py.services.cost_tracker import cost_tracker
    cost_tracker.add_lines_changed(new_lines, original_lines)
    return {"file_path": str(path), "bytes": len(content.encode("utf-8"))}


def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
    **_: Any,
) -> dict[str, Any]:
    path = _path(file_path)
    assert_read_before_write(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    count = content.count(old_string)
    if count == 0:
        raise ValueError("old_string was not found")
    if count > 1 and not replace_all:
        raise ValueError("old_string is not unique; pass replace_all=true to replace every match")
    updated = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
    path.write_text(updated, encoding="utf-8")
    update_after_write(path, updated)
    replacements = count if replace_all else 1
    old_lines = (old_string.count('\n') + 1) * replacements
    new_lines = (new_string.count('\n') + 1) * replacements
    from claude_code_py.services.cost_tracker import cost_tracker
    cost_tracker.add_lines_changed(new_lines, old_lines)
    return {"file_path": str(path), "replacements": replacements}
