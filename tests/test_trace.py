from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent.parser import ToolCallAction
from agent.trace import JsonTraceLogger, TraceEvent


def test_log_event_writes_jsonl(tmp_path: Path) -> None:
    trace_file = tmp_path / "trace.jsonl"
    logger = JsonTraceLogger(trace_file)

    event = logger.log_event(
        TraceEvent(
            user_id="user_1",
            session_id="session_1",
            step=1,
            event_type="user_message",
            payload={"content": "hello"},
        )
    )

    lines = trace_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["trace_id"] == event.trace_id
    assert data["user_id"] == "user_1"
    assert data["session_id"] == "session_1"
    assert data["step"] == 1
    assert data["event_type"] == "user_message"
    assert data["status"] == "ok"
    assert data["payload"] == {"content": "hello"}
    assert data["error"] is None
    assert datetime.fromisoformat(data["timestamp"]).tzinfo is not None


def test_log_llm_output_records_raw_output(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    logger.log_llm_output("user_1", "session_1", 2, '{"type": "final"}', duration_ms=12.5)
    event = logger.read_events()[0]

    assert event.event_type == "llm_output"
    assert event.duration_ms == 12.5
    assert event.payload == {"raw_output": '{"type": "final"}'}


def test_log_parse_action_serializes_action(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")
    action = ToolCallAction(
        reason="Need arithmetic.",
        tool_name="calculator",
        arguments={"expression": "23*17"},
    )

    logger.log_parse_action("user_1", "session_1", 3, action)
    event = logger.read_events()[0]

    assert event.event_type == "parse_action"
    assert event.payload["action"]["type"] == "tool_call"
    assert event.payload["action"]["tool_name"] == "calculator"
    assert event.payload["action"]["arguments"] == {"expression": "23*17"}


def test_log_tool_call_and_result_record_tool_details(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    logger.log_tool_call("user_1", "session_1", 4, "calculator", {"expression": "23*17"})
    logger.log_tool_result(
        "user_1",
        "session_1",
        5,
        "calculator",
        {"ok": True, "result": 391},
        duration_ms=3,
    )
    events = logger.read_events()

    assert events[0].event_type == "tool_call"
    assert events[0].payload == {
        "tool_name": "calculator",
        "arguments": {"expression": "23*17"},
    }
    assert events[1].event_type == "tool_result"
    assert events[1].duration_ms == 3
    assert events[1].payload == {
        "tool_name": "calculator",
        "result": {"ok": True, "result": 391},
    }


def test_log_error_records_error_message(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    logger.log_error("user_1", "session_1", 6, ValueError("bad parse"), {"raw": "oops"})
    event = logger.read_events()[0]

    assert event.event_type == "error"
    assert event.status == "error"
    assert event.error == "bad parse"
    assert event.payload == {"raw": "oops"}


def test_log_final_answer_records_answer(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    logger.log_final_answer("user_1", "session_1", 7, "Done.")
    event = logger.read_events()[0]

    assert event.event_type == "final_answer"
    assert event.payload == {"answer": "Done."}


def test_read_events_filters_by_user_and_session(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")
    logger.log_llm_output("alice", "main", 1, "alice-main")
    logger.log_llm_output("alice", "other", 1, "alice-other")
    logger.log_llm_output("bob", "main", 1, "bob-main")

    user_events = logger.read_events(user_id="alice")
    session_events = logger.read_events(session_id="main")
    combined_events = logger.read_events(user_id="alice", session_id="main")

    assert [event.payload["raw_output"] for event in user_events] == ["alice-main", "alice-other"]
    assert [event.payload["raw_output"] for event in session_events] == ["alice-main", "bob-main"]
    assert [event.payload["raw_output"] for event in combined_events] == ["alice-main"]


def test_read_events_limit_returns_recent_entries(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")
    for step in range(5):
        logger.log_llm_output("user_1", "session_1", step, f"output {step}")

    recent = logger.read_events(limit=2)

    assert [event.payload["raw_output"] for event in recent] == ["output 3", "output 4"]


def test_non_json_serializable_payload_is_stringified(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "trace.jsonl")

    logger.log_event(
        TraceEvent(
            user_id="user_1",
            session_id="session_1",
            step=1,
            event_type="tool_result",
            payload={"items": {1, 2, 3}},
        )
    )
    event = logger.read_events()[0]

    assert event.payload == {"items": "{1, 2, 3}"}


def test_missing_trace_file_reads_as_empty_list(tmp_path: Path) -> None:
    logger = JsonTraceLogger(tmp_path / "missing.jsonl")

    assert logger.read_events() == []
