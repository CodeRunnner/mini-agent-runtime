from __future__ import annotations

import json
from pathlib import Path

from agent.runtime import AgentRuntime, FakeLLMClient, RuntimeConfig
from agent.session import JsonSessionStore
from agent.tool_registry import ToolRegistry
from agent.trace import JsonTraceLogger
from tools.calculator import CalculatorTool
from tools.todo import TodoTool
from tools.weather import WeatherTool


def _final(answer: str, reason: str = "Done.") -> str:
    return json.dumps({"type": "final", "reason": reason, "answer": answer})


def _tool_call(tool_name: str, arguments: dict[str, object], reason: str = "Use tool.") -> str:
    return json.dumps(
        {
            "type": "tool_call",
            "reason": reason,
            "tool_name": tool_name,
            "arguments": arguments,
        }
    )


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(WeatherTool())
    registry.register(TodoTool())
    return registry


def _runtime(
    tmp_path: Path,
    responses: list[str],
    *,
    max_steps: int = 5,
    repeat_last: bool = False,
    registry: ToolRegistry | None = None,
) -> tuple[AgentRuntime, FakeLLMClient, JsonSessionStore, JsonTraceLogger]:
    fake_llm = FakeLLMClient(responses, repeat_last=repeat_last)
    session_store = JsonSessionStore(tmp_path / "sessions")
    trace_logger = JsonTraceLogger(tmp_path / "trace.jsonl")
    runtime = AgentRuntime(
        llm_client=fake_llm,
        tool_registry=registry or _registry(),
        session_store=session_store,
        trace_logger=trace_logger,
        config=RuntimeConfig(max_steps=max_steps),
    )
    return runtime, fake_llm, session_store, trace_logger


def test_final_answer_path_writes_assistant_message(tmp_path: Path) -> None:
    runtime, _fake_llm, session_store, trace_logger = _runtime(
        tmp_path, [_final("Hello from runtime.")]
    )

    answer = runtime.run_turn("user_1", "main", "hello")
    session = session_store.load("user_1", "main")
    event_types = [event.event_type for event in trace_logger.read_events()]

    assert answer == "Hello from runtime."
    assert [message.role for message in session.messages] == ["user", "assistant"]
    assert session.messages[-1].content == "Hello from runtime."
    assert event_types == ["user_message", "llm_output", "parse_action", "final_answer"]


def test_calculator_tool_path_then_final(tmp_path: Path) -> None:
    runtime, fake_llm, session_store, trace_logger = _runtime(
        tmp_path,
        [
            _tool_call("calculator", {"expression": "23*17"}),
            _final("23 * 17 = 391"),
        ],
    )

    answer = runtime.run_turn("user_1", "main", "calculate 23 * 17")
    session = session_store.load("user_1", "main")
    event_types = [event.event_type for event in trace_logger.read_events()]
    second_context = "\n".join(message["content"] for message in fake_llm.calls[1])

    assert answer == "23 * 17 = 391"
    assert session.tool_results[0].tool_name == "calculator"
    assert session.tool_results[0].result == {"ok": True, "result": 391}
    assert session.messages[-2].role == "tool"
    assert "391" in second_context
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "final_answer" in event_types


def test_multi_step_weather_todo_then_final(tmp_path: Path) -> None:
    runtime, _fake_llm, session_store, trace_logger = _runtime(
        tmp_path,
        [
            _tool_call("weather", {"city": "Shanghai"}),
            _tool_call("todo", {"action": "add", "text": "Review Shanghai weather"}),
            _final("Weather checked and todo added."),
        ],
    )

    answer = runtime.run_turn("user_1", "main", "check weather and remember it")
    session = session_store.load("user_1", "main")
    event_types = [event.event_type for event in trace_logger.read_events()]

    assert answer == "Weather checked and todo added."
    assert session.tool_results[0].tool_name == "weather"
    assert session.tool_results[1].tool_name == "todo"
    assert session.todos == [{"id": 1, "text": "Review Shanghai weather", "done": False}]
    assert event_types.count("tool_call") == 2
    assert event_types.count("tool_result") == 2


def test_session_aware_todo_isolated_by_session(tmp_path: Path) -> None:
    session_store = JsonSessionStore(tmp_path / "sessions")
    trace_logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    runtime_1 = AgentRuntime(
        llm_client=FakeLLMClient(
            [_tool_call("todo", {"action": "add", "text": "Window one todo"}), _final("done")]
        ),
        tool_registry=_registry(),
        session_store=session_store,
        trace_logger=trace_logger,
    )
    runtime_2 = AgentRuntime(
        llm_client=FakeLLMClient(
            [_tool_call("todo", {"action": "add", "text": "Window two todo"}), _final("done")]
        ),
        tool_registry=_registry(),
        session_store=session_store,
        trace_logger=trace_logger,
    )

    runtime_1.run_turn("user_1", "window_1", "add todo")
    runtime_2.run_turn("user_1", "window_2", "add todo")

    window_1 = session_store.load("user_1", "window_1")
    window_2 = session_store.load("user_1", "window_2")

    assert window_1.todos == [{"id": 1, "text": "Window one todo", "done": False}]
    assert window_2.todos == [{"id": 1, "text": "Window two todo", "done": False}]


def test_max_steps_prevents_infinite_loop(tmp_path: Path) -> None:
    runtime, fake_llm, session_store, trace_logger = _runtime(
        tmp_path,
        [_tool_call("calculator", {"expression": "1 + 1"})],
        max_steps=2,
        repeat_last=True,
    )

    answer = runtime.run_turn("user_1", "main", "loop forever")
    session = session_store.load("user_1", "main")
    events = trace_logger.read_events()

    assert answer == "Runtime error: max steps exceeded (2)"
    assert fake_llm.call_count == 2
    assert len(session.tool_results) == 2
    assert events[-1].event_type == "error"
    assert events[-1].error == "Runtime error: max steps exceeded (2)"


def test_parse_error_records_trace_error(tmp_path: Path) -> None:
    runtime, _fake_llm, session_store, trace_logger = _runtime(tmp_path, ["not valid json"])

    answer = runtime.run_turn("user_1", "main", "trigger parse error")
    session = session_store.load("user_1", "main")
    errors = [event for event in trace_logger.read_events() if event.event_type == "error"]

    assert answer.startswith("Runtime error: failed to parse LLM output")
    assert session.messages[-1].role == "assistant"
    assert errors
    assert errors[0].payload == {"raw_output": "not valid json"}


def test_missing_tool_is_recorded_and_loop_continues(tmp_path: Path) -> None:
    runtime, _fake_llm, session_store, trace_logger = _runtime(
        tmp_path,
        [_tool_call("missing_tool", {"value": 1}), _final("Handled missing tool.")],
    )

    answer = runtime.run_turn("user_1", "main", "call missing tool")
    session = session_store.load("user_1", "main")
    errors = [event for event in trace_logger.read_events() if event.event_type == "error"]

    assert answer == "Handled missing tool."
    assert session.tool_results[0].tool_name == "missing_tool"
    assert session.tool_results[0].result == {
        "ok": False,
        "error": "tool not found: missing_tool",
    }
    assert errors
    assert errors[0].payload == {
        "tool_name": "missing_tool",
        "arguments": {"value": 1},
    }


def test_trace_logger_records_runtime_lifecycle(tmp_path: Path) -> None:
    runtime, _fake_llm, _session_store, trace_logger = _runtime(
        tmp_path,
        [_tool_call("calculator", {"expression": "2 + 2"}), _final("4")],
    )

    runtime.run_turn("user_1", "main", "calculate")
    event_types = [event.event_type for event in trace_logger.read_events()]

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
