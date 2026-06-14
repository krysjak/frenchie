from __future__ import annotations

import sys
import time
import os
from claude_code_py.config import RuntimeConfig
from claude_code_py.messages import Message, create_user_message
from claude_code_py.permissions import PermissionContext
from claude_code_py.prompts import load_prompt_bundle
from claude_code_py.services.claude_client import ClaudeClient
from claude_code_py.services.session_store import SessionStore
from claude_code_py.tools.orchestrator import extract_tool_uses, run_tool_uses
from claude_code_py.logger import get_logger


log = get_logger("query")


# ── Color Constants ──────────────────────────────────────────────────────────
CLAUDE_ORANGE = "\033[38;5;203m"   # red (#e5484d)
ACCENT_CYAN   = "\033[38;5;210m"   # light red (#ff8787)
ACCENT_GREEN  = "\033[38;5;114m"   # #5fd787
ACCENT_YELLOW = "\033[38;5;221m"   # #ffd75f
TEXT_DIM      = "\033[38;5;242m"
TEXT_THINKING = "\033[3;38;5;244m" # dim italic
RESET         = "\033[0m"
BOLD          = "\033[1m"
DIM           = "\033[2m"
ITALIC        = "\033[3m"


def _safe(s: str, fallback: str) -> str:
    try:
        enc = sys.stdout.encoding or "utf-8"
        s.encode(enc)
        return s
    except Exception:
        return fallback


CHECK  = _safe("✔", "[ok]")
ARROW  = _safe("▸", ">")
BULLET = _safe("·", "-")
THINK_DOT = _safe("●", "*")


def _assistant_text(content: object) -> str:
    if isinstance(content, dict):
        content = content.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def _print_thinking_header() -> None:
    """Print a styled thinking indicator."""
    print(f"  {CLAUDE_ORANGE}{THINK_DOT}{RESET} {DIM}Thinking…{RESET}", flush=True)


def _print_thinking_done(duration: float) -> None:
    """Print thinking completion."""
    print(f"\r\033[K", end="")
    dur_str = f"{duration:.1f}s" if duration >= 1 else f"{duration * 1000:.0f}ms"
    print(
        f"  {ACCENT_GREEN}{CHECK}{RESET} {DIM}Thought for {dur_str}{RESET}",
        flush=True,
    )


def _print_thinking_chunk(chunk: str) -> None:
    """Print a thinking chunk in dim italic, indented."""
    lines = chunk.split("\n")
    for i, line in enumerate(lines):
        if i > 0:
            print(f"\n    {TEXT_THINKING}{line}{RESET}", end="", flush=True)
        else:
            print(f"{TEXT_THINKING}{line}{RESET}", end="", flush=True)


_response_header_printed = False


def _print_response_header() -> None:
    """Print a subtle separator before Claude's response."""
    global _response_header_printed
    if not _response_header_printed:
        print(f"\n  {CLAUDE_ORANGE}{ARROW}{RESET} ", end="", flush=True)
        _response_header_printed = True


def _reset_response_header() -> None:
    global _response_header_printed
    _response_header_printed = False


def _print_text_chunk(chunk: str) -> None:
    """Print a text chunk with a leading indicator on first chunk.
    Uses markdown_renderer for rich formatting when available."""
    _print_response_header()
    print(chunk, end="", flush=True)


def _render_final_markdown(text: str) -> None:
    """Render the final accumulated text with Markdown formatting.

    Called after streaming is complete to apply rich formatting.
    """
    if not text.strip():
        return
    try:
        from claude_code_py.components.markdown_renderer import render_markdown
        render_markdown(text)
    except ImportError:
        # Fallback: plain text
        print(text)


def run_turn_loop(
    client: ClaudeClient,
    store: SessionStore,
    messages: list[Message],
    system_prompt: str,
    stream: bool,
    max_turns: int,
    permission_context: PermissionContext | None = None,
) -> str:
    log.debug("Starting turn loop — max_turns=%d, stream=%s, messages=%d", max_turns, stream, len(messages))
    text = ""
    if permission_context is None:
        permission_context = PermissionContext()
    printed_stream = False
    _reset_response_header()

    for turn in range(max_turns):
        if stream:
            from claude_code_py.tui import ThinkingSpinner
            current_mode = None  # None, "thinking", "text"
            start_thinking_time = None
            _accumulated_text = ""

            spinner = ThinkingSpinner("Thinking")
            spinner.start()
            spinner_active = True

            def handle_thinking(chunk: str) -> None:
                nonlocal current_mode, start_thinking_time, printed_stream, spinner_active
                if spinner_active:
                    spinner.stop()
                    spinner_active = False
                if current_mode != "thinking":
                    if current_mode == "text":
                        print()  # newline after text
                    current_mode = "thinking"
                    start_thinking_time = time.perf_counter()
                    _print_thinking_header()
                _print_thinking_chunk(chunk)
                printed_stream = True

            def handle_text(chunk: str) -> None:
                nonlocal current_mode, start_thinking_time, printed_stream, _accumulated_text, spinner_active
                if spinner_active:
                    spinner.stop()
                    spinner_active = False
                if current_mode == "thinking":
                    duration = time.perf_counter() - start_thinking_time if start_thinking_time else 0.0
                    print()  # newline after thinking
                    _print_thinking_done(duration)
                    _reset_response_header()  # fresh header for text after thinking
                current_mode = "text"
                _accumulated_text += chunk
                _print_text_chunk(chunk)
                printed_stream = True

            import inspect
            sig = inspect.signature(client.stream_complete)
            kwargs = {}
            if "on_text" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["on_text"] = handle_text
            if "on_thinking" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs["on_thinking"] = handle_thinking

            try:
                assistant = client.stream_complete(messages, system_prompt, **kwargs)
            finally:
                if spinner_active:
                    spinner.stop()
                    spinner_active = False

            if current_mode == "thinking" and start_thinking_time:
                duration = time.perf_counter() - start_thinking_time
                print()  # newline
                _print_thinking_done(duration)
        else:
            from claude_code_py.tui import ThinkingSpinner
            spinner = ThinkingSpinner("Thinking")
            spinner.start()
            try:
                assistant = client.complete(messages, system_prompt)
            finally:
                spinner.stop()

        store.append(assistant)
        messages.append(assistant)
        from claude_code_py.components.status_bar import get_status_bar
        from claude_code_py.services.cost_tracker import cost_tracker
        get_status_bar().update(cost=cost_tracker.total_cost_usd)
        text = _assistant_text(assistant.content)
        tool_uses = extract_tool_uses(
            assistant.content.get("content") if isinstance(assistant.content, dict) else assistant.content
        )
        if not tool_uses:
            if stream and printed_stream:
                print()
            # Render final text with Markdown formatting (if not already streamed raw)
            if stream and _accumulated_text and os.environ.get("FRENCH_MARKDOWN_RENDER") == "1":
                _render_final_markdown(_accumulated_text)
            log.debug("Turn %d complete — no tool uses, returning text (%d chars)", turn, len(text))
            return text
        log.debug("Turn %d — %d tool use(s) detected", turn, len(tool_uses))

        # Run tools
        if stream and printed_stream:
            print()  # spacing before tools

        tool_results = run_tool_uses(tool_uses, permission_context)
        user_tool_result = create_user_message(tool_results)
        store.append(user_tool_result)
        messages.append(user_tool_result)

    if stream and printed_stream:
        print()
    return text


def run_single_turn(config: RuntimeConfig, prompt: str, stream: bool = True, max_turns: int = 5) -> str:
    log.info("Single turn — prompt=%s..., stream=%s", prompt[:60], stream)
    from claude_code_py.services.cost_tracker import cost_tracker
    cost_tracker.load_from_state(config.home)

    from claude_code_py.services.mcp.client import initialize_mcp_servers
    initialize_mcp_servers(config.home, config.cwd)

    store = SessionStore(config.home, config.cwd)
    client = ClaudeClient(config.model)
    client.validate()
    user_message = create_user_message(prompt)
    store.append(user_message)
    system_prompt = load_prompt_bundle().render_system_prompt(config.model)
    messages = [user_message]
    try:
        res = run_turn_loop(client, store, messages, system_prompt, stream=stream, max_turns=max_turns)
    finally:
        cost_tracker.save_to_state(config.home)
    log.info("Single turn complete — response=%d chars", len(res))
    return res
