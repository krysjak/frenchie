# Python Port Status

## Completed

- Created Python package scaffold in `claude_code_py`.
- Added CLI entrypoint `python -m claude_code_py`.
- Added early environment setup matching the TypeScript bootstrap behavior where practical.
- Added UTF-8 console output handling for Windows.
- Copied all 17 prompt markdown files into `claude_code_py/resources/prompts`.
- Added prompt bundle loader and `--dump-system-prompt`.
- Added command registry scaffold.
- Added tool registry scaffold.
- Ported first working tool batch: `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash`, `TodoWrite`, `WebFetch`.
- Added `tool` CLI command with inline JSON and `--payload-file` execution.
- Copied tool prompt source files into `claude_code_py/resources/tool_prompts`.
- Added Python command model and ported first command batch: `help`, `doctor`, `status`, `config/settings`, `memory`, `files`.
- Added message dataclasses, JSONL session storage, and Anthropic client wrapper.
- Added `run` command for single-turn API execution when `ANTHROPIC_API_KEY` is configured.
- Added Python MCP explorer with `mcp tools`, `mcp call`, and JSON-RPC stdio handler.
- Added permission model and tool-use orchestration scaffold.
- Added task store and task tools: `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`, `TaskStop`.
- Added MCP resource tools: `ListMcpResourcesTool`, `ReadMcpResourceTool`.
- Added plan mode tools: `EnterPlanMode`, `ExitPlanMode`.
- Added `Config` tool and `permissions` / `allowed-tools` command.
- Added `CLAUDE_CONFIG_HOME` support for isolated config testing.
- Added shell safety checks for `Bash` and `PowerShell`.
- Added tool aliases for backward compatibility: `Task` -> `Agent`, `KillShell` -> `TaskStop`.
- Added partial local implementations for `PowerShell`, `NotebookEdit`, `ToolSearch`, `Skill`, `Agent`, `TeamCreate`, `TeamDelete`, and `SendMessage`.
- Added persistent read state plus read-before-write and stale-read enforcement for `Read`, `Write`, `Edit`, and `NotebookEdit`.
- Added smoke checks for filesystem, notebook, task, tool-search, and permission behavior.
- Added streamed conversation turn-loop support so streamed responses preserve `tool_use` blocks, execute tools, append `tool_result`, and continue to the final assistant message.
- Added partial image handling for `Read` with MIME detection, dimensions, base64 image blocks, and structured tool-result content.
- Added partial notebook `Read` handling that renders cells and notebook outputs into structured tool-result blocks instead of raw `.ipynb` JSON.
- Added partial PDF `Read` handling with PDF validation, page-range parsing, page-count metadata, and base64 document tool-result blocks.
- Added partial text `Read` safety limits with binary extension/content detection and configurable max-size checks.
- Added partial local shell task lifecycle support: `Bash`/`PowerShell` background spawning, PID/output metadata, `TaskGet` refresh, and real `TaskStop` termination for shell tasks.
- Added migration manifest generator.
- Generated `port-manifest.json` with 2,094 source files.
- Current manifest status: 127 `ported`, 0 `in_progress`, 1,904 `pending`, 63 `intentionally_replaced`.
- Ported additional command handlers: `commit`, `init`, `version`.

## Pending

- Port all command handlers from `src/commands`.
- Port all tools from `src/tools`.
- Port the main loop, message model, context builder, and streaming engine.
- Port MCP client/server behavior.
- Port settings, auth, policy, analytics, telemetry, session storage, and migrations.
- Replace TSX terminal UI with a Python terminal UI.
- Decide whether the `web` directory is ported to Python backend templates, kept as a web frontend, or rewritten separately.

## Rule

Every source file must be marked in `port-manifest.json` as one of:

- `pending`
- `in_progress`
- `ported`
- `intentionally_replaced`
- `not_applicable`
