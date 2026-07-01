from __future__ import annotations

from agent.context import (
    BasicContextCompressor,
    ContextBuilder,
    ContextConfig,
    estimate_context_size,
)
from agent.session import Message, SessionState, ToolResult


def _content(messages: list[dict[str, str]]) -> str:
    return "\n".join(message["content"] for message in messages)


def test_build_messages_contains_system_prompt_and_tool_schemas() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    tool_schemas = [
        {
            "name": "calculator",
            "description": "Evaluate arithmetic.",
            "parameters": {"type": "object"},
        }
    ]

    messages = ContextBuilder().build_messages(state, tool_schemas)
    combined = _content(messages)

    assert messages[0]["role"] == "system"
    assert "You must output JSON only" in messages[0]["content"]
    assert "calculator" in combined
    assert "Evaluate arithmetic." in combined


def test_build_messages_contains_session_summary() -> None:
    state = SessionState(
        user_id="user_1",
        session_id="session_1",
        summary="The user is building a mini agent runtime.",
    )

    messages = ContextBuilder().build_messages(state, [])

    assert "The user is building a mini agent runtime." in _content(messages)


def test_build_messages_contains_todos_as_structured_state() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    state.todos.append({"id": 1, "text": "Wire TodoTool to SessionState", "done": False})

    messages = ContextBuilder().build_messages(state, [])
    combined = _content(messages)

    assert "Structured session state" in combined
    assert "Wire TodoTool to SessionState" in combined
    assert '"done": false' in combined


def test_build_messages_only_includes_recent_messages() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    for index in range(5):
        state.messages.append(Message(role="user", content=f"message {index}"))
    builder = ContextBuilder(ContextConfig(recent_message_limit=2))

    messages = builder.build_messages(state, [])
    combined = _content(messages)

    assert "message 0" not in combined
    assert "message 1" not in combined
    assert "message 2" not in combined
    assert "message 3" in combined
    assert "message 4" in combined


def test_build_messages_only_includes_recent_tool_results() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    for index in range(4):
        state.tool_results.append(
            ToolResult(
                tool_name=f"tool_{index}",
                arguments={"index": index},
                result={"ok": True, "value": index},
            )
        )
    builder = ContextBuilder(ContextConfig(recent_tool_result_limit=2))

    messages = builder.build_messages(state, [])
    combined = _content(messages)

    assert "tool_0" not in combined
    assert "tool_1" not in combined
    assert "tool_2" in combined
    assert "tool_3" in combined


def test_long_tool_result_is_truncated() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    state.tool_results.append(
        ToolResult(
            tool_name="search",
            arguments={"query": "long"},
            result={"text": "x" * 200},
        )
    )
    builder = ContextBuilder(ContextConfig(max_tool_result_chars=40))

    messages = builder.build_messages(state, [])
    combined = _content(messages)

    assert "...[truncated]" in combined
    assert "x" * 120 not in combined


def test_should_compress_when_message_count_exceeds_threshold() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    for index in range(4):
        state.messages.append(Message(role="user", content=f"message {index}"))
    compressor = BasicContextCompressor(ContextConfig(compress_trigger_message_count=3))

    assert compressor.should_compress(state) is True


def test_compress_updates_summary_and_keeps_recent_messages() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    state.summary = "Existing facts."
    for index in range(6):
        state.messages.append(Message(role="user", content=f"user goal {index}"))
    compressor = BasicContextCompressor(ContextConfig(keep_recent_after_compress=2))

    compressed = compressor.compress(state)

    assert "Existing facts." in compressed.summary
    assert "user goal 0" in compressed.summary
    assert [message.content for message in compressed.messages] == ["user goal 4", "user goal 5"]


def test_compress_does_not_delete_todos() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    state.todos.append({"id": 1, "text": "Keep this todo", "done": False})
    for index in range(5):
        state.messages.append(Message(role="user", content=f"message {index}"))
    compressor = BasicContextCompressor(ContextConfig(keep_recent_after_compress=2))

    compressed = compressor.compress(state)

    assert compressed.todos == [{"id": 1, "text": "Keep this todo", "done": False}]


def test_context_does_not_include_full_trace() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")
    state.trace = [{"trace_id": "trace-123", "payload": "debug event"}]

    messages = ContextBuilder().build_messages(state, [])
    combined = _content(messages)

    assert "trace-123" not in combined
    assert "debug event" not in combined


def test_system_prompt_requires_json_and_short_reason() -> None:
    state = SessionState(user_id="user_1", session_id="session_1")

    messages = ContextBuilder().build_messages(state, [])
    system_prompt = messages[0]["content"]

    assert "output JSON only" in system_prompt
    assert '"tool_call"' in system_prompt
    assert '"final"' in system_prompt
    assert "reason is only a short debugging explanation" in system_prompt
    assert "do not output full chain-of-thought" in system_prompt


def test_estimate_context_size_counts_strings_and_messages() -> None:
    assert estimate_context_size("abc") == 3
    assert estimate_context_size([{"role": "user", "content": "hello"}]) > 5
