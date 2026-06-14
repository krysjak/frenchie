from __future__ import annotations

import json
import os
import base64
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_code_py.permissions import PermissionContext, decide_permission
from claude_code_py.messages import Message, create_assistant_message
from claude_code_py.query import run_turn_loop
from claude_code_py.tools import tool_registry
from claude_code_py.tools.filesystem import FILE_UNCHANGED_STUB, edit_file, read_file, write_file
from claude_code_py.tools.notebook import notebook_edit
from claude_code_py.tools.shell import bash
from claude_code_py.tools.tasks import task_create, task_get, task_list, task_stop, task_update
from claude_code_py.tools.tool_search import tool_search


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeStore:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def append(self, message: Message) -> None:
        self.messages.append(message)


class FakeStreamingClient:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.turn = 0

    def stream_complete(self, messages: list[Message], system: str | None = None, on_text=None) -> Message:
        self.turn += 1
        if self.turn == 1:
            return create_assistant_message(
                [{"type": "tool_use", "id": "toolu_smoke", "name": "Read", "input": {"file_path": str(self.path)}}],
                request_id="req_tool",
            )
        if on_text:
            on_text("done")
        return create_assistant_message([{"type": "text", "text": "done"}], request_id="req_done")


def main() -> None:
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            root = Path(tmp)
            os.chdir(root)

            sample = root / "sample.txt"
            sample.write_text("alpha\n", encoding="utf-8")
            try:
                edit_file(str(sample), "alpha", "beta")
                raise AssertionError("edit without read should fail")
            except ValueError as exc:
                expect("not been read" in str(exc), "unexpected missing-read error")

            read_file(str(sample))
            unchanged = read_file(str(sample))
            expect(unchanged["content"] == FILE_UNCHANGED_STUB, "second read should return unchanged stub")
            edit_file(str(sample), "alpha", "beta")
            expect(sample.read_text(encoding="utf-8") == "beta\n", "edit should update file")

            stream_store = FakeStore()
            text = run_turn_loop(
                FakeStreamingClient(sample),
                stream_store,  # type: ignore[arg-type]
                [],
                "",
                stream=True,
                max_turns=3,
            )
            expect(text == "done", "streaming tool loop should return final text")
            expect(
                any(
                    message.type == "user"
                    and isinstance(message.content, dict)
                    and isinstance(message.content.get("content"), list)
                    and message.content["content"][0].get("type") == "tool_result"
                    for message in stream_store.messages
                ),
                "streaming tool loop should append tool_result",
            )

            created = root / "created.txt"
            write_file(str(created), "new")
            expect(created.read_text(encoding="utf-8") == "new", "write should create file")

            task = task_create("Smoke", "Run smoke checks")["task"]
            task_update(task["id"], status="in_progress")
            expect(task_get(task["id"])["task"]["status"] == "in_progress", "task update should persist")
            expect(len(task_list()["tasks"]) == 1, "task list should include created task")

            notebook = root / "test.ipynb"
            notebook.write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "id": "abc",
                                "metadata": {},
                                "source": "print(1)",
                                "execution_count": 1,
                                "outputs": [],
                            }
                        ],
                        "metadata": {"language_info": {"name": "python"}},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )
            notebook_read = read_file(str(notebook))
            expect('<cell id="abc">' in notebook_read["content"], "notebook read should render cells")
            expect(notebook_read["_tool_result_content"][0]["type"] == "text", "notebook read should return text blocks")
            result = notebook_edit(str(notebook), "print(2)", cell_id="abc")
            expect(result["cell_id"] == "abc", "notebook edit should target cell")
            expect("NotebookEdit" in tool_search("notebook edit")["matches"], "tool search should find NotebookEdit")

            png = root / "pixel.png"
            png.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                )
            )
            image_result = read_file(str(png))
            expect(image_result["media_type"] == "image/png", "image read should detect png")
            expect(image_result["width"] == 1 and image_result["height"] == 1, "image read should include dimensions")
            expect(image_result["_tool_result_content"][0]["type"] == "image", "image read should include image block")

            pdf = root / "one-page.pdf"
            pdf.write_bytes(
                b"%PDF-1.4\n"
                b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
                b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
                b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Contents 4 0 R >> endobj\n"
                b"4 0 obj << /Length 44 >> stream\nBT /F1 12 Tf 10 10 Td (Hello) Tj ET\nendstream endobj\n"
                b"trailer << /Root 1 0 R >>\n%%EOF\n"
            )
            pdf_result = read_file(str(pdf), pages="1")
            expect(pdf_result["media_type"] == "application/pdf", "pdf read should detect pdf")
            expect(pdf_result["pages"] == 1, "pdf read should include page count when available")
            expect(pdf_result["_tool_result_content"][0]["type"] == "document", "pdf read should include document block")
            read_schema = next(schema for schema in tool_registry.api_schemas() if schema["name"] == "Read")
            expect("pages" in read_schema["input_schema"]["properties"], "Read schema should expose pdf pages")
            expect("cell_id" in read_schema["input_schema"]["properties"], "Read schema should expose notebook cell_id")
            bash_schema = next(schema for schema in tool_registry.api_schemas() if schema["name"] == "Bash")
            expect("run_in_background" in bash_schema["input_schema"]["properties"], "Bash schema should expose background mode")

            bg_command = f'"{sys.executable}" -c "import time; print(\'start\', flush=True); time.sleep(30)"'
            background = bash(bg_command, run_in_background=True)
            expect(background["status"] == "in_progress", "background bash should create running task")
            shell_task = task_get(background["task_id"])["task"]
            expect(shell_task["pid"] == background["pid"], "TaskGet should expose shell pid")
            stopped = task_stop(task_id=background["task_id"])
            expect(stopped["task_type"] == "local_shell", "TaskStop should stop shell task")
            expect(task_get(background["task_id"])["task"]["status"] == "cancelled", "stopped shell task should be cancelled")

            binary = root / "data.bin"
            binary.write_bytes(b"\x00\x01\x02")
            try:
                read_file(str(binary))
                raise AssertionError("binary extension read should fail")
            except ValueError as exc:
                expect("binary" in str(exc), "unexpected binary extension error")

            oversized = root / "oversized.txt"
            oversized.write_text("x" * 32, encoding="utf-8")
            old_limit = os.environ.get("CLAUDE_CODE_FILE_READ_MAX_SIZE_BYTES")
            os.environ["CLAUDE_CODE_FILE_READ_MAX_SIZE_BYTES"] = "8"
            try:
                try:
                    read_file(str(oversized))
                    raise AssertionError("oversized read should fail")
                except ValueError as exc:
                    expect("maximum allowed size" in str(exc), "unexpected oversized read error")
            finally:
                if old_limit is None:
                    os.environ.pop("CLAUDE_CODE_FILE_READ_MAX_SIZE_BYTES", None)
                else:
                    os.environ["CLAUDE_CODE_FILE_READ_MAX_SIZE_BYTES"] = old_limit

            expect(decide_permission("Read", PermissionContext()).behavior == "allow", "Read should be allowed")
            expect(decide_permission("Write", PermissionContext()).behavior == "ask", "Write should ask by default")
        finally:
            os.chdir(old_cwd)

    print("smoke ok")


if __name__ == "__main__":
    main()
