from __future__ import annotations

from .filesystem import edit_file, read_file, write_file
from .config_tool import config_tool
from .agent import agent
from .mcp_resources import list_mcp_resources, read_mcp_resource
from .plan_mode import enter_plan_mode, exit_plan_mode
from .notebook import notebook_edit
from .registry import Tool, tool_registry
from .search import glob_files, grep
from .shell import bash, powershell
from .skill import skill
from .tasks import task_create, task_get, task_list, task_stop, task_update
from .team import send_message, team_create, team_delete
from .todo import todo_write
from .tool_search import tool_search
from .web import web_fetch, web_search


def register_builtin_tools() -> None:
    definitions = [
        Tool(
            "Bash",
            "Execute a shell command.",
            bash,
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_ms": {"type": "integer"},
                    "description": {"type": "string"},
                    "run_in_background": {"type": "boolean"},
                    "dangerouslyDisableSandbox": {"type": "boolean"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            "Read",
            "Read a file from the local filesystem.",
            read_file,
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "pages": {"type": "string"},
                    "cell_id": {"type": "string"},
                },
                "required": ["file_path"],
            },
            read_only=True,
        ),
        Tool(
            "Write",
            "Write a file to the local filesystem.",
            write_file,
            {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]},
        ),
        Tool(
            "Edit",
            "Perform exact string replacements in files.",
            edit_file,
            {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean"},
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        ),
        Tool(
            "Glob",
            "Fast file pattern matching tool.",
            glob_files,
            {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]},
            read_only=True,
        ),
        Tool(
            "Grep",
            "Search files using ripgrep when available.",
            grep,
            {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                    "glob": {"type": "string"},
                    "output_mode": {"type": "string"},
                    "multiline": {"type": "boolean"},
                    "case_insensitive": {"type": "boolean"},
                },
                "required": ["pattern"],
            },
            read_only=True,
        ),
        Tool(
            "TodoWrite",
            "Write the current todo list.",
            todo_write,
            {"type": "object", "properties": {"todos": {"type": "array"}, "file_path": {"type": "string"}}, "required": ["todos"]},
        ),
        Tool(
            "WebFetch",
            "Fetch a URL and return text content.",
            web_fetch,
            {"type": "object", "properties": {"url": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["url"]},
            read_only=True,
        ),
        Tool(
            "WebSearch",
            "Search the web through a configured provider.",
            web_search,
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            read_only=True,
        ),
        Tool(
            "TaskCreate",
            "Create a task in the task list.",
            task_create,
            {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                    "activeForm": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["subject", "description"],
            },
        ),
        Tool(
            "TaskGet",
            "Retrieve a task by ID.",
            task_get,
            {"type": "object", "properties": {"taskId": {"type": "string"}}, "required": ["taskId"]},
            read_only=True,
        ),
        Tool(
            "TaskUpdate",
            "Update a task.",
            task_update,
            {
                "type": "object",
                "properties": {
                    "taskId": {"type": "string"},
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                    "activeForm": {"type": "string"},
                    "status": {"type": "string"},
                    "addBlocks": {"type": "array", "items": {"type": "string"}},
                    "addBlockedBy": {"type": "array", "items": {"type": "string"}},
                    "owner": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["taskId"],
            },
        ),
        Tool(
            "TaskList",
            "List all tasks.",
            task_list,
            {"type": "object", "properties": {}},
            read_only=True,
        ),
        Tool(
            "TaskStop",
            "Stop a running background task by ID.",
            task_stop,
            {
                "type": "object",
                "properties": {"task_id": {"type": "string"}, "shell_id": {"type": "string"}},
            },
            aliases=("KillShell",),
        ),
        Tool(
            "ListMcpResourcesTool",
            "List resources from connected MCP servers.",
            list_mcp_resources,
            {"type": "object", "properties": {"server": {"type": "string"}}},
            read_only=True,
        ),
        Tool(
            "ReadMcpResourceTool",
            "Read a specific MCP resource by URI.",
            read_mcp_resource,
            {"type": "object", "properties": {"server": {"type": "string"}, "uri": {"type": "string"}}, "required": ["server", "uri"]},
            read_only=True,
        ),
        Tool(
            "EnterPlanMode",
            "Requests permission to enter plan mode for complex tasks requiring exploration and design.",
            enter_plan_mode,
            {"type": "object", "properties": {}},
            read_only=True,
        ),
        Tool(
            "ExitPlanMode",
            "Prompts the user to exit plan mode and start coding.",
            exit_plan_mode,
            {"type": "object", "properties": {"allowedPrompts": {"type": "array"}}},
        ),
        Tool(
            "Config",
            "Get or set Frenchie configuration settings.",
            config_tool,
            {
                "type": "object",
                "properties": {
                    "setting": {"type": "string"},
                    "value": {"anyOf": [{"type": "string"}, {"type": "boolean"}, {"type": "number"}]},
                },
                "required": ["setting"],
            },
        ),
        Tool(
            "PowerShell",
            "Execute a PowerShell command.",
            powershell,
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                    "description": {"type": "string"},
                    "run_in_background": {"type": "boolean"},
                    "dangerouslyDisableSandbox": {"type": "boolean"},
                },
                "required": ["command"],
            },
        ),
        Tool(
            "NotebookEdit",
            "Edit Jupyter notebook cells (.ipynb).",
            notebook_edit,
            {
                "type": "object",
                "properties": {
                    "notebook_path": {"type": "string"},
                    "cell_id": {"type": "string"},
                    "new_source": {"type": "string"},
                    "cell_type": {"type": "string", "enum": ["code", "markdown"]},
                    "edit_mode": {"type": "string", "enum": ["replace", "insert", "delete"]},
                },
                "required": ["notebook_path", "new_source"],
            },
        ),
        Tool(
            "ToolSearch",
            "Search over available tools.",
            tool_search,
            {
                "type": "object",
                "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
                "required": ["query"],
            },
            read_only=True,
        ),
        Tool(
            "Skill",
            "Execute or expand a local skill prompt.",
            skill,
            {
                "type": "object",
                "properties": {"skill": {"type": "string"}, "args": {"type": "string"}},
                "required": ["skill"],
            },
            read_only=True,
        ),
        Tool(
            "Agent",
            "Launch a new agent.",
            agent,
            {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "prompt": {"type": "string"},
                    "subagent_type": {"type": "string"},
                    "model": {"type": "string", "enum": ["sonnet", "opus", "haiku"]},
                    "run_in_background": {"type": "boolean"},
                    "name": {"type": "string"},
                    "team_name": {"type": "string"},
                    "mode": {"type": "string"},
                    "isolation": {"type": "string"},
                    "cwd": {"type": "string"},
                },
                "required": ["description", "prompt"],
            },
            aliases=("Task",),
        ),
        Tool(
            "TeamCreate",
            "Create a new team for coordinating multiple agents.",
            team_create,
            {
                "type": "object",
                "properties": {"team_name": {"type": "string"}, "description": {"type": "string"}, "agent_type": {"type": "string"}},
                "required": ["team_name"],
            },
        ),
        Tool(
            "TeamDelete",
            "Clean up team and task directories when the swarm is complete.",
            team_delete,
            {"type": "object", "properties": {"team_name": {"type": "string"}}},
        ),
        Tool(
            "SendMessage",
            "Send a message to a teammate inbox.",
            send_message,
            {
                "type": "object",
                "properties": {"to": {"type": "string"}, "summary": {"type": "string"}, "message": {}, "team_name": {"type": "string"}},
                "required": ["to", "message"],
            },
        ),
    ]
    for definition in definitions:
        tool_registry.register(definition)


register_builtin_tools()
