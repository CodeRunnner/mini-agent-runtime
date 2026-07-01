"""Display JSONL trace events for a user/session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from agent.trace import JsonTraceLogger, TraceEvent


def event_to_display(event: TraceEvent) -> dict[str, object]:
    """Return a compact JSON-serializable event payload."""
    data = event.to_dict()
    return {
        "timestamp": data["timestamp"],
        "user_id": data["user_id"],
        "session_id": data["session_id"],
        "step": data["step"],
        "event_type": data["event_type"],
        "status": data["status"],
        "payload": data["payload"],
        "error": data["error"],
    }


def read_trace_events(
    trace_file: str | Path,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int | None = None,
) -> list[TraceEvent]:
    """Read events from a trace file with optional filters."""
    return JsonTraceLogger(trace_file).read_events(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the trace display script."""
    parser = argparse.ArgumentParser(description="Show mini-agent-runtime trace events.")
    parser.add_argument("--trace-file", default="data/traces/trace.jsonl")
    parser.add_argument("--user", dest="user_id")
    parser.add_argument("--session", dest="session_id")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)

    events = read_trace_events(
        args.trace_file,
        user_id=args.user_id,
        session_id=args.session_id,
        limit=args.limit,
    )
    if not events:
        print("No trace events found.")
        return 1

    for event in events:
        print(json.dumps(event_to_display(event), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
