from __future__ import annotations

import os
import time
import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from claude_code_py.messages import Message, create_assistant_message, normalize_for_api
from claude_code_py.tools import tool_registry
from claude_code_py.services.cost_tracker import cost_tracker


class ClaudeClientError(RuntimeError):
    pass


def map_tools_to_openai(anthropic_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    openai_tools = []
    for schema in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema.get("description", ""),
                "parameters": schema.get("input_schema", {"type": "object", "properties": {}})
            }
        })
    return openai_tools


def map_messages_to_openai(anthropic_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    openai_msgs = []
    for msg in anthropic_messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        tool_result_content = block.get("content", "")
                        if not isinstance(tool_result_content, str):
                            tool_result_content = json.dumps(tool_result_content)
                        openai_msgs.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id"),
                            "content": tool_result_content
                        })
                    elif block.get("type") == "text":
                        openai_msgs.append({
                            "role": "user",
                            "content": block.get("text", "")
                        })
            else:
                openai_msgs.append({
                    "role": "user",
                    "content": content
                })

        elif role == "assistant":
            if isinstance(content, list):
                text_content = ""
                tool_calls = []
                for block in content:
                    if block.get("type") == "thinking":
                        text_content += f"<thinking>\n{block.get('thinking', '')}\n</thinking>\n"
                    elif block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })

                openai_msg: dict[str, Any] = {"role": "assistant"}
                if text_content:
                    openai_msg["content"] = text_content
                else:
                    openai_msg["content"] = None

                if tool_calls:
                    openai_msg["tool_calls"] = tool_calls
                openai_msgs.append(openai_msg)
            else:
                openai_msgs.append({
                    "role": "assistant",
                    "content": content
                })
    return openai_msgs


class StreamingResponseParser:
    def __init__(self, on_thinking: Callable[[str], None], on_text: Callable[[str], None]):
        self.on_thinking = on_thinking
        self.on_text = on_text
        self.buffer = ""
        self.in_thinking = False

    def feed(self, chunk: str) -> None:
        self.buffer += chunk

        while self.buffer:
            tags = ["<thinking>", "<thought>", "</thinking>", "</thought>"]
            earliest_idx = -1
            earliest_tag = None

            for tag in tags:
                idx = self.buffer.find(tag)
                if idx != -1:
                    if earliest_idx == -1 or idx < earliest_idx:
                        earliest_idx = idx
                        earliest_tag = tag

            if earliest_tag is not None:
                pre_tag_content = self.buffer[:earliest_idx]
                if pre_tag_content:
                    if self.in_thinking:
                        self.on_thinking(pre_tag_content)
                    else:
                        self.on_text(pre_tag_content)

                if earliest_tag in ("<thinking>", "<thought>"):
                    self.in_thinking = True
                elif earliest_tag in ("</thinking>", "</thought>"):
                    self.in_thinking = False

                self.buffer = self.buffer[earliest_idx + len(earliest_tag):]
            else:
                # Keep up to 12 chars to avoid cutting a tag in half
                safe_len = len(self.buffer) - 12
                if safe_len > 0:
                    safe_content = self.buffer[:safe_len]
                    if self.in_thinking:
                        self.on_thinking(safe_content)
                    else:
                        self.on_text(safe_content)
                    self.buffer = self.buffer[safe_len:]
                break

    def flush(self) -> None:
        if self.buffer:
            if self.in_thinking:
                self.on_thinking(self.buffer)
            else:
                self.on_text(self.buffer)
            self.buffer = ""



class ClaudeClient:
    def __init__(self, model: str, api_key: str | None = None, max_tokens: int = 4096) -> None:
        self.model = model
        from claude_code_py.config import RuntimeConfig
        config = RuntimeConfig.from_environment()
        self.api_provider = config.api_provider
        self.api_base_url = config.api_base_url

        if api_key:
            self.api_key = api_key
        else:
            from claude_code_py.services.auth import get_auth_token
            self.api_key = get_auth_token(config.home)
        self.max_tokens = max_tokens

    def _client(self) -> Any:
        if self.api_provider != "anthropic":
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ClaudeClientError("The 'openai' Python package is not installed") from exc
            api_key = self.api_key or "lm-studio"
            return OpenAI(api_key=api_key, base_url=self.api_base_url)
        else:
            if not self.api_key:
                raise ClaudeClientError("ANTHROPIC_API_KEY is not set")
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise ClaudeClientError("The 'anthropic' Python package is not installed") from exc
            return Anthropic(api_key=self.api_key)

    def validate(self) -> None:
        client = self._client()
        if self.api_provider != "anthropic":
            try:
                client.models.list()
            except Exception:
                pass

    def complete(self, messages: list[Message], system: str | None = None) -> Message:
        client = self._client()

        if self.api_provider != "anthropic":
            openai_msgs = []
            if system:
                openai_msgs.append({"role": "system", "content": system})
            openai_msgs.extend(map_messages_to_openai(normalize_for_api(messages)))
            openai_tools = map_tools_to_openai(tool_registry.api_schemas())

            params: dict[str, Any] = {
                "model": self.model,
                "messages": openai_msgs,
                "max_tokens": self.max_tokens,
            }
            if openai_tools:
                params["tools"] = openai_tools

            start_time = time.perf_counter()
            response = client.chat.completions.create(**params)
            duration = time.perf_counter() - start_time

            choice_msg = response.choices[0].message
            content = []
            if choice_msg.content:
                content.append({"type": "text", "text": choice_msg.content})
            if choice_msg.tool_calls:
                for tc in choice_msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": args
                    })

            self._record_cost_openai(response, duration)
            return create_assistant_message(content, request_id=response.id)

        else:
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": normalize_for_api(messages),
                "tools": tool_registry.api_schemas(),
            }
            if system:
                params["system"] = system
            start_time = time.perf_counter()
            response = client.messages.create(**params)
            duration = time.perf_counter() - start_time
            self._record_cost(response, duration)
            return self._message_from_response(response)

    def _record_cost(self, response: Any, duration: float) -> None:
        cost_tracker.add_api_duration(duration)
        usage = getattr(response, "usage", None)
        if usage:
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
            web_search = 0
            server_tool_use = getattr(usage, "server_tool_use", None)
            if server_tool_use:
                web_search = getattr(server_tool_use, "web_search_requests", 0) or 0
            cost_tracker.add_usage(
                self.model,
                input_tokens,
                output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_write,
                web_search_requests=web_search,
            )

    def _record_cost_openai(self, response: Any, duration: float) -> None:
        cost_tracker.add_api_duration(duration)
        usage = getattr(response, "usage", None)
        if usage:
            input_tokens = getattr(usage, "prompt_tokens", 0)
            output_tokens = getattr(usage, "completion_tokens", 0)
            cost_tracker.add_usage(
                self.model,
                input_tokens,
                output_tokens,
            )

    def _message_from_response(self, response: Any) -> Message:
        content: list[dict[str, Any]] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "thinking":
                content.append({"type": "thinking", "thinking": getattr(block, "thinking", "")})
            elif block_type == "text":
                content.append({"type": "text", "text": block.text})
            elif block_type == "tool_use":
                content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return create_assistant_message(content, request_id=getattr(response, "id", None))

    def stream_complete(
        self,
        messages: list[Message],
        system: str | None = None,
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ) -> Message:
        client = self._client()

        if self.api_provider != "anthropic":
            openai_msgs = []
            if system:
                openai_msgs.append({"role": "system", "content": system})
            openai_msgs.extend(map_messages_to_openai(normalize_for_api(messages)))
            openai_tools = map_tools_to_openai(tool_registry.api_schemas())

            params: dict[str, Any] = {
                "model": self.model,
                "messages": openai_msgs,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            if openai_tools:
                params["tools"] = openai_tools

            start_time = time.perf_counter()
            response_stream = client.chat.completions.create(**params)

            accumulated_text = ""
            accumulated_thinking = ""
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            def handle_thinking_chunk(t: str) -> None:
                nonlocal accumulated_thinking
                accumulated_thinking += t
                if on_thinking:
                    on_thinking(t)

            def handle_text_chunk(t: str) -> None:
                nonlocal accumulated_text
                accumulated_text += t
                if on_text:
                    on_text(t)

            parser = StreamingResponseParser(on_thinking=handle_thinking_chunk, on_text=handle_text_chunk)

            for chunk in response_stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Try to extract reasoning_content (OpenAI standard)
                reasoning_part = getattr(delta, "reasoning_content", None)
                if reasoning_part:
                    handle_thinking_chunk(reasoning_part)
                    continue

                if getattr(delta, "content", None):
                    parser.feed(delta.content)

                if getattr(delta, "tool_calls", None):
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": ""
                            }

                        if getattr(tc_delta, "id", None):
                            accumulated_tool_calls[idx]["id"] += tc_delta.id
                        if getattr(tc_delta, "function", None):
                            func = tc_delta.function
                            if getattr(func, "name", None):
                                accumulated_tool_calls[idx]["name"] += func.name
                            if getattr(func, "arguments", None):
                                accumulated_tool_calls[idx]["arguments"] += func.arguments

            parser.flush()

            duration = time.perf_counter() - start_time
            cost_tracker.add_api_duration(duration)

            content = []
            if accumulated_thinking:
                content.append({"type": "thinking", "thinking": accumulated_thinking})
            if accumulated_text:
                content.append({"type": "text", "text": accumulated_text})
            for idx, tc in sorted(accumulated_tool_calls.items()):
                try:
                    args = json.loads(tc["arguments"])
                except Exception:
                    args = {}
                content.append({
                    "type": "tool_use",
                    "id": tc["id"] or f"toolu_{uuid.uuid4().hex[:8]}",
                    "name": tc["name"],
                    "input": args
                })

            return create_assistant_message(content)

        else:
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": normalize_for_api(messages),
                "tools": tool_registry.api_schemas(),
            }
            if system:
                params["system"] = system

            # Enable thinking for models that support it
            # All Claude 3.7+, 4.x, and Fable 5 models support extended thinking
            _thinking_models = (
                "claude-3-7-sonnet", "claude-sonnet-4-5", "claude-sonnet-4-6",
                "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
                "claude-fable-5",
            )
            if any(m in self.model for m in _thinking_models):
                # Effort-based thinking budget
                effort = os.environ.get("FRENCH_EFFORT") or os.environ.get("CLAUDE_EFFORT") or "high"
                effort_budgets = {"low": 1024, "medium": 2048, "high": 4096, "xhigh": 8192}
                budget = effort_budgets.get(effort, 4096)
                if (os.environ.get("FRENCH_THINKING_DISABLED") or os.environ.get("CLAUDE_THINKING_DISABLED")) != "1":
                    params["thinking"] = {
                        "type": "enabled",
                        "budget_tokens": budget
                    }
                    # Ensure max_tokens is larger than thinking budget
                    params["max_tokens"] = max(self.max_tokens, budget + 1024)

            start_time = time.perf_counter()
            with client.messages.stream(**params) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "thinking_delta":
                            thinking_val = getattr(delta, "thinking", None)
                            if thinking_val and on_thinking:
                                on_thinking(thinking_val)
                        elif delta_type == "text_delta":
                            text_val = getattr(delta, "text", None)
                            if text_val and on_text:
                                on_text(text_val)
                final_message = stream.get_final_message()
            duration = time.perf_counter() - start_time
            self._record_cost(final_message, duration)
            return self._message_from_response(final_message)

    def stream_text(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        client = self._client()
        if self.api_provider != "anthropic":
            openai_msgs = []
            if system:
                openai_msgs.append({"role": "system", "content": system})
            openai_msgs.extend(map_messages_to_openai(normalize_for_api(messages)))
            response_stream = client.chat.completions.create(
                model=self.model,
                messages=openai_msgs,
                max_tokens=self.max_tokens,
                stream=True
            )
            for chunk in response_stream:
                if chunk.choices and getattr(chunk.choices[0].delta, "content", None):
                    yield chunk.choices[0].delta.content
        else:
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": normalize_for_api(messages),
                "tools": tool_registry.api_schemas(),
            }
            if system:
                params["system"] = system
            with client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text
