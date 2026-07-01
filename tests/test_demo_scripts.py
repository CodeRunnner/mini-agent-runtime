from __future__ import annotations

import json
from pathlib import Path

from agent.session import JsonSessionStore
from agent.trace import JsonTraceLogger
from scripts.demo_compress import run_demo
from scripts.show_session import main as show_session_main
from scripts.show_trace import main as show_trace_main


def test_show_trace_displays_filtered_events(tmp_path: Path, capsys) -> None:
    trace_file = tmp_path / "data" / "traces" / "trace.jsonl"
    logger = JsonTraceLogger(trace_file)
    logger.log_llm_output("user_1", "session_1", 1, "raw")
    logger.log_final_answer("user_2", "session_2", 1, "done")

    result = show_trace_main(
        [
            "--trace-file",
            str(trace_file),
            "--user",
            "user_1",
            "--session",
            "session_1",
            "--limit",
            "5",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    lines = [json.loads(line) for line in captured.out.splitlines()]
    assert len(lines) == 1
    assert lines[0]["event_type"] == "llm_output"
    assert lines[0]["payload"] == {"raw_output": "raw"}


def test_show_session_displays_existing_session(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "data"
    store = JsonSessionStore(data_dir / "sessions")
    store.append_message("user_1", "session_1", "user", "hello")
    store.append_tool_result("user_1", "session_1", "calculator", {"expression": "1+1"}, {"ok": True, "result": 2})

    result = show_session_main(
        ["--data-dir", str(data_dir), "--user", "user_1", "--session", "session_1"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert payload["user_id"] == "user_1"
    assert payload["session_id"] == "session_1"
    assert payload["message_count"] == 1
    assert payload["tool_result_count"] == 1


def test_demo_compress_creates_compressed_session(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "data", "user_1", "compress_window", message_count=25)

    assert result["compressed"] is True
    assert result["before_messages"] == 25
    assert result["after_messages"] == 8
    assert result["summary_chars"] > 0
