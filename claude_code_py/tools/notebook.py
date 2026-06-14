from __future__ import annotations

import json
import random
import string
from pathlib import Path
from typing import Any

from claude_code_py.services.read_state import assert_read_before_write, update_after_write

LARGE_OUTPUT_THRESHOLD = 10000


def _source_text(source: str | list[str] | None) -> str:
    if source is None:
        return ""
    return "".join(source) if isinstance(source, list) else str(source)


def _output_text(text: str | list[str] | None) -> str:
    return _source_text(text)


def _extract_output_image(data: dict[str, Any] | None) -> dict[str, str] | None:
    if not data:
        return None
    if isinstance(data.get("image/png"), str):
        return {"image_data": str(data["image/png"]).replace("\n", ""), "media_type": "image/png"}
    if isinstance(data.get("image/jpeg"), str):
        return {"image_data": str(data["image/jpeg"]).replace("\n", ""), "media_type": "image/jpeg"}
    return None


def _process_output(output: dict[str, Any]) -> dict[str, Any]:
    output_type = output.get("output_type")
    if output_type == "stream":
        return {"output_type": output_type, "text": _output_text(output.get("text"))}
    if output_type in {"execute_result", "display_data"}:
        data = output.get("data") if isinstance(output.get("data"), dict) else {}
        return {
            "output_type": output_type,
            "text": _output_text(data.get("text/plain")),
            "image": _extract_output_image(data),
        }
    if output_type == "error":
        traceback = output.get("traceback") if isinstance(output.get("traceback"), list) else []
        return {
            "output_type": output_type,
            "text": f"{output.get('ename', '')}: {output.get('evalue', '')}\n" + "\n".join(str(line) for line in traceback),
        }
    return {"output_type": output_type or "unknown", "text": ""}


def _outputs_are_large(outputs: list[dict[str, Any]]) -> bool:
    size = 0
    for output in outputs:
        image = output.get("image") or {}
        size += len(str(output.get("text") or "")) + len(str(image.get("image_data") or ""))
        if size > LARGE_OUTPUT_THRESHOLD:
            return True
    return False


def read_notebook(notebook_path: str, cell_id: str | None = None) -> dict[str, Any]:
    path = Path(notebook_path).expanduser()
    if not path.is_absolute():
        raise ValueError("notebook_path must be absolute")
    notebook = json.loads(path.read_text(encoding="utf-8-sig"))
    language = notebook.get("metadata", {}).get("language_info", {}).get("name", "python")
    cells = notebook.get("cells", [])
    if cell_id:
        matches = [cell for cell in cells if cell.get("id") == cell_id]
        if not matches:
            raise ValueError(f'Cell with ID "{cell_id}" not found in notebook')
        cells = matches

    processed: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        actual_index = notebook.get("cells", []).index(cell) if cell in notebook.get("cells", []) else index
        cell_type = cell.get("cell_type", "code")
        cell_data: dict[str, Any] = {
            "cellType": cell_type,
            "source": _source_text(cell.get("source")),
            "cell_id": cell.get("id") or f"cell-{actual_index}",
        }
        if cell_type == "code":
            cell_data["language"] = language
            if cell.get("execution_count") is not None:
                cell_data["execution_count"] = cell.get("execution_count")
            outputs = [_process_output(output) for output in cell.get("outputs", []) if isinstance(output, dict)]
            if outputs:
                if not cell_id and _outputs_are_large(outputs):
                    cell_data["outputs"] = [
                        {
                            "output_type": "stream",
                            "text": f"Outputs are too large to include. Use Bash with: cat <notebook_path> | jq '.cells[{actual_index}].outputs'",
                        }
                    ]
                else:
                    cell_data["outputs"] = outputs
        processed.append(cell_data)
    return {"notebook_path": str(path), "language": language, "cells": processed}


def notebook_cells_to_tool_result(data: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for cell in data["cells"]:
        metadata = []
        if cell["cellType"] != "code":
            metadata.append(f"<cell_type>{cell['cellType']}</cell_type>")
        if cell.get("language") and cell.get("language") != "python" and cell["cellType"] == "code":
            metadata.append(f"<language>{cell['language']}</language>")
        blocks.append({"type": "text", "text": f"<cell id=\"{cell['cell_id']}\">{''.join(metadata)}{cell['source']}</cell id=\"{cell['cell_id']}\">"})
        for output in cell.get("outputs", []):
            if output.get("text"):
                blocks.append({"type": "text", "text": "\n" + output["text"]})
            image = output.get("image")
            if image:
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": image["media_type"], "data": image["image_data"]},
                    }
                )
    merged: list[dict[str, Any]] = []
    for block in blocks:
        if merged and merged[-1]["type"] == "text" and block["type"] == "text":
            merged[-1]["text"] += "\n" + block["text"]
        else:
            merged.append(block)
    return merged


def _cell_index(cells: list[dict[str, Any]], cell_id: str | None) -> int:
    if not cell_id:
        return 0
    for index, cell in enumerate(cells):
        if cell.get("id") == cell_id:
            return index
    if cell_id.startswith("cell-"):
        value = int(cell_id.removeprefix("cell-"))
        if 0 <= value <= len(cells):
            return value
    raise ValueError(f'Cell with ID "{cell_id}" not found in notebook.')


def _new_cell_id() -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))


def notebook_edit(
    notebook_path: str,
    new_source: str,
    cell_id: str | None = None,
    cell_type: str | None = None,
    edit_mode: str = "replace",
) -> dict[str, Any]:
    path = Path(notebook_path).expanduser()
    if not path.is_absolute():
        raise ValueError("notebook_path must be absolute")
    if path.suffix != ".ipynb":
        raise ValueError("File must be a Jupyter notebook (.ipynb file).")
    if edit_mode not in {"replace", "insert", "delete"}:
        raise ValueError("edit_mode must be replace, insert, or delete")
    if edit_mode == "insert" and not cell_type:
        raise ValueError("cell_type is required when edit_mode=insert")

    assert_read_before_write(path)
    original = path.read_text(encoding="utf-8-sig")
    notebook = json.loads(original)
    cells = notebook.setdefault("cells", [])
    index = _cell_index(cells, cell_id)
    if edit_mode == "insert" and cell_id:
        index += 1
    if edit_mode == "replace" and index == len(cells):
        edit_mode = "insert"
        cell_type = cell_type or "code"

    language = notebook.get("metadata", {}).get("language_info", {}).get("name", "python")
    output_cell_id = cell_id
    if edit_mode == "delete":
        if index >= len(cells):
            raise ValueError("Cell index is out of range")
        removed = cells.pop(index)
        output_cell_id = removed.get("id", cell_id)
        output_cell_type = removed.get("cell_type", cell_type or "code")
    elif edit_mode == "insert":
        output_cell_id = _new_cell_id()
        output_cell_type = cell_type or "code"
        cell: dict[str, Any] = {"cell_type": output_cell_type, "id": output_cell_id, "metadata": {}, "source": new_source}
        if output_cell_type == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.insert(index, cell)
    else:
        if index >= len(cells):
            raise ValueError("Cell index is out of range")
        cell = cells[index]
        cell["source"] = new_source
        if cell.get("cell_type") == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        if cell_type:
            cell["cell_type"] = cell_type
        output_cell_type = cell.get("cell_type", cell_type or "code")
        output_cell_id = cell.get("id", cell_id)

    updated = json.dumps(notebook, indent=1, ensure_ascii=False)
    path.write_text(updated, encoding="utf-8")
    update_after_write(path, updated)
    return {
        "new_source": new_source,
        "cell_id": output_cell_id,
        "cell_type": output_cell_type,
        "language": language,
        "edit_mode": edit_mode,
        "notebook_path": str(path),
        "original_file": original,
        "updated_file": updated,
    }
