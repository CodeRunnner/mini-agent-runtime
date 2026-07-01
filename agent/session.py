"""Session state and JSON persistence for mini-agent-runtime."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from agent.context import AgentContext


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    """A conversation message stored in a session."""

    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass
class ToolResult:
    """A tool execution result stored in a session."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass
class SessionState:
    """Persistent state isolated by user_id and session_id."""

    user_id: str
    session_id: str
    status: str = "idle"
    summary: str = ""
    messages: list[Message] = field(default_factory=list)
    todos: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the session state to JSON-compatible data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Restore session state from JSON-compatible data."""
        return cls(
            user_id=str(data["user_id"]),
            session_id=str(data["session_id"]),
            status=str(data.get("status", "idle")),
            summary=str(data.get("summary", "")),
            messages=[
                message if isinstance(message, Message) else Message(**message)
                for message in data.get("messages", [])
            ],
            todos=list(data.get("todos", [])),
            tool_results=[
                result if isinstance(result, ToolResult) else ToolResult(**result)
                for result in data.get("tool_results", [])
            ],
            created_at=str(data.get("created_at", _utc_now_iso())),
            updated_at=str(data.get("updated_at", _utc_now_iso())),
        )


class JsonSessionStore:
    """Local JSON-backed session store."""

    _safe_id_pattern = re.compile(r"[^A-Za-z0-9._-]+")

    def __init__(self, base_dir: str | Path = Path("data") / "sessions") -> None:
        self.base_dir = Path(base_dir)

    def load(self, user_id: str, session_id: str) -> SessionState:
        """Load a session, creating it when no persisted state exists."""
        path = self._session_path(user_id, session_id)
        if not path.exists():
            state = SessionState(user_id=user_id, session_id=session_id)
            self.save(state)
            return state

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return SessionState.from_dict(data)

    def save(self, session_state: SessionState) -> None:
        """Persist a session as readable JSON."""
        session_state.updated_at = _utc_now_iso()
        path = self._session_path(session_state.user_id, session_state.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(session_state.to_dict(), file, indent=2, ensure_ascii=False)

    def append_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """Append a message and persist the session."""
        state = self.load(user_id, session_id)
        state.messages.append(Message(role=role, content=content, metadata=metadata or {}))
        self.save(state)
        return state

    def append_tool_result(
        self,
        user_id: str,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> SessionState:
        """Append a tool result and persist the session."""
        state = self.load(user_id, session_id)
        state.tool_results.append(
            ToolResult(tool_name=tool_name, arguments=arguments, result=result)
        )
        self.save(state)
        return state

    def get_recent_messages(
        self, user_id: str, session_id: str, limit: int = 8
    ) -> list[Message]:
        """Return the most recent messages without modifying the session."""
        if limit <= 0:
            return []
        state = self.load(user_id, session_id)
        return state.messages[-limit:]

    def update_summary(self, user_id: str, session_id: str, summary: str) -> SessionState:
        """Update and persist a session summary."""
        state = self.load(user_id, session_id)
        state.summary = summary
        self.save(state)
        return state

    def _session_path(self, user_id: str, session_id: str) -> Path:
        safe_user_id = self._safe_id(user_id)
        safe_session_id = self._safe_id(session_id)
        base_dir = self.base_dir.resolve()
        path = (base_dir / safe_user_id / f"{safe_session_id}.json").resolve()
        if not path.is_relative_to(base_dir):
            raise ValueError("session path escapes base_dir")
        return path

    @classmethod
    def _safe_id(cls, value: str) -> str:
        raw = str(value).strip()
        safe = raw.replace("/", "_").replace("\\", "_")
        safe = safe.replace("..", "_")
        safe = cls._safe_id_pattern.sub("_", safe)
        safe = safe.strip("._-")
        return safe or "default"


@dataclass
class AgentSession:
    """Minimal session container kept for compatibility."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    context: AgentContext = field(default_factory=AgentContext)
