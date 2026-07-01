"""JSONL trace logging for agent runtime observability."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceEvent:
    """Single runtime trace event."""

    user_id: str
    session_id: str
    step: int
    event_type: str
    status: str = "ok"
    duration_ms: float | None = None
    payload: Any = field(default_factory=dict)
    error: str | None = None
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to JSON-compatible data."""
        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "step": self.step,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "payload": _make_json_safe(self.payload),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        """Restore a trace event from JSON data."""
        return cls(
            trace_id=str(data.get("trace_id") or uuid4()),
            user_id=str(data["user_id"]),
            session_id=str(data["session_id"]),
            step=int(data["step"]),
            event_type=str(data["event_type"]),
            timestamp=str(data.get("timestamp") or _utc_now_iso()),
            status=str(data.get("status", "ok")),
            duration_ms=data.get("duration_ms"),
            payload=data.get("payload", {}),
            error=data.get("error"),
        )


class JsonTraceLogger:
    """Append-only JSONL trace logger."""

    def __init__(self, trace_file: str | Path = Path("data") / "traces" / "trace.jsonl") -> None:
        self.trace_file = Path(trace_file)

    def log_event(self, event: TraceEvent) -> TraceEvent:
        """Write an event as one JSONL line.

        Trace logging is observational. If the trace file cannot be written, the
        logger swallows the I/O error so the main runtime flow is not interrupted.
        """
        try:
            self.trace_file.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_file.open("a", encoding="utf-8") as file:
                file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass
        return event

    def log_llm_output(
        self,
        user_id: str,
        session_id: str,
        step: int,
        raw_output: str,
        duration_ms: float | None = None,
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="llm_output",
                duration_ms=duration_ms,
                payload={"raw_output": raw_output},
            )
        )

    def log_parse_action(
        self,
        user_id: str,
        session_id: str,
        step: int,
        action: Any,
        duration_ms: float | None = None,
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="parse_action",
                duration_ms=duration_ms,
                payload={"action": _make_json_safe(action)},
            )
        )

    def log_tool_call(
        self,
        user_id: str,
        session_id: str,
        step: int,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="tool_call",
                payload={"tool_name": tool_name, "arguments": arguments},
            )
        )

    def log_tool_result(
        self,
        user_id: str,
        session_id: str,
        step: int,
        tool_name: str,
        result: Any,
        duration_ms: float | None = None,
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="tool_result",
                duration_ms=duration_ms,
                payload={"tool_name": tool_name, "result": result},
            )
        )

    def log_final_answer(
        self, user_id: str, session_id: str, step: int, answer: str
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="final_answer",
                payload={"answer": answer},
            )
        )

    def log_error(
        self,
        user_id: str,
        session_id: str,
        step: int,
        error: Exception | str,
        payload: Any | None = None,
    ) -> TraceEvent:
        return self.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=step,
                event_type="error",
                status="error",
                payload=payload or {},
                error=str(error),
            )
        )

    def read_events(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[TraceEvent]:
        """Read trace events, optionally filtered and limited to recent entries."""
        if not self.trace_file.exists():
            return []

        events: list[TraceEvent] = []
        with self.trace_file.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    event = TraceEvent.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
                if user_id is not None and event.user_id != user_id:
                    continue
                if session_id is not None and event.session_id != session_id:
                    continue
                events.append(event)

        if limit is not None:
            if limit <= 0:
                return []
            return events[-limit:]
        return events


@dataclass
class Trace:
    """Small in-memory trace container kept for compatibility."""

    events: list[TraceEvent] = field(default_factory=list)

    def add(
        self,
        event_type: str,
        payload: Any | None = None,
        *,
        user_id: str = "",
        session_id: str = "",
        step: int = 0,
        status: str = "ok",
        error: str | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            user_id=user_id,
            session_id=session_id,
            step=step,
            event_type=event_type,
            status=status,
            payload=payload or {},
            error=error,
        )
        self.events.append(event)
        return event


def _make_json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _make_json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value
