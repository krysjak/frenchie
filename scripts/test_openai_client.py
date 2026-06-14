import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from claude_code_py.messages import create_user_message, create_assistant_message
from claude_code_py.services.claude_client import map_messages_to_openai, map_tools_to_openai


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    # Test tool mapping
    anthropic_tools = [
        {
            "name": "Read",
            "description": "Read file",
            "input_schema": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
            },
        }
    ]
    openai_tools = map_tools_to_openai(anthropic_tools)
    expect(len(openai_tools) == 1, "Should map one tool")
    expect(openai_tools[0]["type"] == "function", "Should be function type")
    expect(openai_tools[0]["function"]["name"] == "Read", "Name should match")

    # Test messages mapping
    user_msg = create_user_message("Hello")
    tool_result_msg = create_user_message(
        [{"type": "tool_result", "tool_use_id": "call_123", "content": "file contents"}]
    )
    assistant_msg = create_assistant_message(
        [
            {"type": "text", "text": "let me read"},
            {"type": "tool_use", "id": "call_123", "name": "Read", "input": {"file_path": "a.txt"}},
        ]
    )

    history = [user_msg, assistant_msg, tool_result_msg]
    api_messages = [msg.content for msg in history]

    openai_msgs = map_messages_to_openai(api_messages)

    expect(len(openai_msgs) == 3, f"Should result in 3 OpenAI messages, got {len(openai_msgs)}")
    expect(openai_msgs[0]["role"] == "user", "First role user")
    expect(openai_msgs[0]["content"] == "Hello", "First content match")

    expect(openai_msgs[1]["role"] == "assistant", "Second role assistant")
    expect("tool_calls" in openai_msgs[1], "Second should have tool_calls")
    expect(openai_msgs[1]["tool_calls"][0]["id"] == "call_123", "Tool call ID matches")

    expect(openai_msgs[2]["role"] == "tool", "Third role tool")
    expect(openai_msgs[2]["tool_call_id"] == "call_123", "Third tool call ID matches")

    # Test mapping assistant with thinking blocks
    thinking_assistant_msg = create_assistant_message(
        [
            {"type": "thinking", "thinking": "let me think"},
            {"type": "text", "text": "here is my answer"}
        ]
    )
    mapped_thinking = map_messages_to_openai([thinking_assistant_msg.content])
    expect(len(mapped_thinking) == 1, "Should map one message")
    expect("<thinking>\nlet me think\n</thinking>" in mapped_thinking[0]["content"], "Should include thinking tags in mapped OpenAI content")
    expect("here is my answer" in mapped_thinking[0]["content"], "Should include text content in mapped OpenAI content")

    # Test StreamingResponseParser
    from claude_code_py.services.claude_client import StreamingResponseParser
    
    thinking_chunks = []
    text_chunks = []
    
    def on_thinking(t):
        thinking_chunks.append(t)
        
    def on_text(t):
        text_chunks.append(t)
        
    parser = StreamingResponseParser(on_thinking, on_text)
    
    # Feed stream in chunks
    parser.feed("Start ")
    parser.feed("<thinking>I should look at ")
    parser.feed("the files </thinking>End response")
    parser.flush()
    
    expect("".join(text_chunks) == "Start End response", f"Expected text, got: {''.join(text_chunks)}")
    expect("".join(thinking_chunks) == "I should look at the files ", f"Expected thinking, got: {''.join(thinking_chunks)}")

    print("OpenAI client mapper test: OK")


if __name__ == "__main__":
    main()
