from __future__ import annotations

import json
from pathlib import Path

from agent.cli import build_tool_registry
from agent.llm_client import FakeLLMClient
from agent.runtime import AgentRuntime, RuntimeConfig
from agent.session import JsonSessionStore
from agent.trace import JsonTraceLogger


def _final(answer: str) -> str:
    return json.dumps({"type": "final", "reason": "done", "answer": answer})


def _tool(tool_name: str, arguments: dict[str, object]) -> str:
    return json.dumps(
        {
            "type": "tool_call",
            "reason": "use tool",
            "tool_name": tool_name,
            "arguments": arguments,
        }
    )


def _runtime(
    tmp_path: Path,
    responses: list[str],
    *,
    max_steps: int = 5,
    repeat_last: bool = False,
) -> tuple[AgentRuntime, JsonSessionStore, JsonTraceLogger]:
    session_store = JsonSessionStore(tmp_path / "data" / "sessions")
    trace_logger = JsonTraceLogger(tmp_path / "data" / "traces" / "trace.jsonl")
    runtime = AgentRuntime(
        llm_client=FakeLLMClient(responses, repeat_last=repeat_last),
        tool_registry=build_tool_registry(),
        session_store=session_store,
        trace_logger=trace_logger,
        config=RuntimeConfig(max_steps=max_steps),
    )
    return runtime, session_store, trace_logger


def test_e2e_fake_calculator_tool_result_final_answer(tmp_path: Path) -> None:
    runtime, session_store, trace_logger = _runtime(
        tmp_path,
        [
            _tool("calculator", {"expression": "23*17"}),
            _final("23 * 17 = 391"),
        ],
    )

    answer = runtime.run_turn("user_a", "window_1", "calculate 23 * 17")
    session = session_store.load("user_a", "window_1")
    events = trace_logger.read_events(user_id="user_a", session_id="window_1")
    event_types = [event.event_type for event in events]

    assert answer == "23 * 17 = 391"
    assert session.messages[0].role == "user"
    assert session.messages[-1].role == "assistant"
    assert session.messages[-1].content == "23 * 17 = 391"
    assert session.tool_results[0].tool_name == "calculator"
    assert session.tool_results[0].result == {"ok": True, "result": 391}
    assert (tmp_path / "data" / "sessions" / "user_a" / "window_1.json").exists()
    assert (tmp_path / "data" / "traces" / "trace.jsonl").exists()
    assert event_types == [
        "user_message",
        "llm_output",
        "parse_action",
        "tool_call",
        "tool_result",
        "llm_output",
        "parse_action",
        "final_answer",
    ]


def test_e2e_fake_todo_add_list_flow(tmp_path: Path) -> None:
    runtime, session_store, trace_logger = _runtime(
        tmp_path,
        [
            _tool("todo", {"action": "add", "text": "record MVP demo"}),
            _tool("todo", {"action": "list"}),
            _final("Todo recorded and listed."),
        ],
    )

    answer = runtime.run_turn("user_a", "window_1", "add and list a todo")
    session = session_store.load("user_a", "window_1")
    events = trace_logger.read_events()

    assert answer == "Todo recorded and listed."
    assert session.todos == [{"id": 1, "text": "record MVP demo", "done": False}]
    assert session.tool_results[0].result == {
        "ok": True,
        "item": {"id": 1, "text": "record MVP demo", "done": False},
    }
    assert session.tool_results[1].result == {
        "ok": True,
        "items": [{"id": 1, "text": "record MVP demo", "done": False}],
    }
    assert [event.event_type for event in events].count("tool_result") == 2


def test_e2e_same_user_window_sessions_are_isolated(tmp_path: Path) -> None:
    session_store = JsonSessionStore(tmp_path / "data" / "sessions")
    trace_logger = JsonTraceLogger(tmp_path / "data" / "traces" / "trace.jsonl")

    runtime_1 = AgentRuntime(
        llm_client=FakeLLMClient(
            [_tool("todo", {"action": "add", "text": "window one"}), _final("done")]
        ),
        tool_registry=build_tool_registry(),
        session_store=session_store,
        trace_logger=trace_logger,
    )
    runtime_2 = AgentRuntime(
        llm_client=FakeLLMClient(
            [_tool("todo", {"action": "add", "text": "window two"}), _final("done")]
        ),
        tool_registry=build_tool_registry(),
        session_store=session_store,
        trace_logger=trace_logger,
    )

    runtime_1.run_turn("user_a", "window_1", "add todo")
    runtime_2.run_turn("user_a", "window_2", "add todo")

    window_1 = session_store.load("user_a", "window_1")
    window_2 = session_store.load("user_a", "window_2")

    assert window_1.todos == [{"id": 1, "text": "window one", "done": False}]
    assert window_2.todos == [{"id": 1, "text": "window two", "done": False}]


def test_e2e_max_steps_stops_infinite_tool_loop(tmp_path: Path) -> None:
    runtime, session_store, trace_logger = _runtime(
        tmp_path,
        [_tool("calculator", {"expression": "1 + 1"})],
        max_steps=2,
        repeat_last=True,
    )

    answer = runtime.run_turn("user_a", "window_1", "loop")
    session = session_store.load("user_a", "window_1")
    errors = [event for event in trace_logger.read_events() if event.event_type == "error"]

    assert answer == "Runtime error: max steps exceeded (2)"
    assert len(session.tool_results) == 2
    assert errors[-1].error == "Runtime error: max steps exceeded (2)"


def test_e2e_parse_error_is_recorded_in_trace(tmp_path: Path) -> None:
    runtime, session_store, trace_logger = _runtime(tmp_path, ["not-json"])

    answer = runtime.run_turn("user_a", "window_1", "break parser")
    session = session_store.load("user_a", "window_1")
    errors = [event for event in trace_logger.read_events() if event.event_type == "error"]

    assert answer.startswith("Runtime error: failed to parse LLM output")
    assert session.messages[-1].content == answer
    assert errors
    assert errors[0].payload == {"raw_output": "not-json"}


def test_e2e_tool_error_is_recorded_in_trace(tmp_path: Path) -> None:
    runtime, session_store, trace_logger = _runtime(
        tmp_path,
        [_tool("missing_tool", {"x": 1}), _final("tool error handled")],
    )

    answer = runtime.run_turn("user_a", "window_1", "call missing tool")
    session = session_store.load("user_a", "window_1")
    errors = [event for event in trace_logger.read_events() if event.event_type == "error"]

    assert answer == "tool error handled"
    assert session.tool_results[0].tool_name == "missing_tool"
    assert session.tool_results[0].result == {
        "ok": False,
        "error": "tool not found: missing_tool",
    }
    assert errors
    assert errors[0].payload == {
        "tool_name": "missing_tool",
        "arguments": {"x": 1},
    }
