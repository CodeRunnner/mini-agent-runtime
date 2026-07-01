"""Conversation context building and basic compression."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


SYSTEM_PROMPT = """You are the model inside mini-agent-runtime.

You must output JSON only. Output exactly one valid JSON object. Do not output
Markdown, prose, code fences, raw numbers, or natural language outside the JSON
object.

Allowed output shapes:
1. Tool call:
{
  "type": "tool_call",
  "reason": "one short decision note, not a full reasoning chain",
  "tool_name": "todo",
  "arguments": {"action": "add", "text": "..."}
}

2. Final answer:
{
  "type": "final",
  "reason": "one short decision note, not a full reasoning chain",
  "answer": "final response text"
}

Rules:
- type must be either "tool_call" or "final".
- tool_call must include tool_name and arguments.
- final must include answer.
- Tool calls must use this exact shape:
  {"type":"tool_call","tool_name":"todo","arguments":{"action":"add","text":"..."}}
- Do not output shortcut tool shapes like {"type":"todo","action":"add","text":"..."}.
- reason is only a short debugging explanation; do not output full chain-of-thought.
- Use available tools only when needed and keep arguments valid for their JSON Schema.
- Even if the final answer is only a number, output a JSON object such as
  {"type":"final","reason":"computed result","answer":"88"}.
- If the user asks for multiple tasks, call the needed tools one by one until
  all tasks are completed, then output a final JSON object.
"""


@dataclass
class ContextConfig:
    """Configuration for context construction."""

    recent_message_limit: int = 8
    recent_tool_result_limit: int = 3
    max_context_chars: int = 12000
    compress_trigger_message_count: int = 20
    keep_recent_after_compress: int = 8
    max_tool_result_chars: int = 1200


@dataclass
class AgentContext:
    """Minimal context container for a future runtime loop."""

    messages: list[dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the context."""
        self.messages.append({"role": role, "content": content})


class ContextBuilder:
    """Build LLM-ready chat messages from session state."""

    def __init__(
        self,
        config: ContextConfig | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.config = config or ContextConfig()
        self.system_prompt = system_prompt

    def build_messages(
        self, session_state: Any, tool_schemas: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        """Build OpenAI-compatible chat messages."""
        recent_messages = list(getattr(session_state, "messages", []))[
            -self.config.recent_message_limit :
        ]
        recent_tool_results = list(getattr(session_state, "tool_results", []))[
            -self.config.recent_tool_result_limit :
        ]

        messages = self._compose_messages(session_state, tool_schemas, recent_tool_results, recent_messages)
        while estimate_context_size(messages) > self.config.max_context_chars and recent_tool_results:
            recent_tool_results = recent_tool_results[1:]
            messages = self._compose_messages(
                session_state, tool_schemas, recent_tool_results, recent_messages
            )

        while estimate_context_size(messages) > self.config.max_context_chars and recent_messages:
            recent_messages = recent_messages[1:]
            messages = self._compose_messages(
                session_state, tool_schemas, recent_tool_results, recent_messages
            )

        return messages

    def _compose_messages(
        self,
        session_state: Any,
        tool_schemas: list[dict[str, Any]],
        recent_tool_results: list[Any],
        recent_messages: list[Any],
    ) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "system",
                "content": "Available tool JSON Schemas:\n"
                + _to_json(_make_json_safe(tool_schemas)),
            },
            {
                "role": "system",
                "content": "Session summary:\n"
                + (str(getattr(session_state, "summary", "")) or "(none)"),
            },
            {
                "role": "system",
                "content": "Structured session state:\n"
                + _to_json(
                    {
                        "user_id": getattr(session_state, "user_id", ""),
                        "session_id": getattr(session_state, "session_id", ""),
                        "status": getattr(session_state, "status", "idle"),
                        "todos": _make_json_safe(getattr(session_state, "todos", [])),
                    }
                ),
            },
            {
                "role": "system",
                "content": "Recent tool results:\n"
                + _to_json([self._tool_result_payload(result) for result in recent_tool_results]),
            },
        ]

        messages.extend(self._message_payload(message) for message in recent_messages)
        return messages

    def _tool_result_payload(self, tool_result: Any) -> dict[str, Any]:
        result = getattr(tool_result, "result", None)
        return {
            "tool_name": getattr(tool_result, "tool_name", ""),
            "arguments": _make_json_safe(getattr(tool_result, "arguments", {})),
            "result": self._truncate_tool_result(result),
            "created_at": getattr(tool_result, "created_at", ""),
        }

    def _truncate_tool_result(self, result: Any) -> Any:
        safe_result = _make_json_safe(result)
        serialized = _to_json(safe_result)
        if len(serialized) <= self.config.max_tool_result_chars:
            return safe_result
        return serialized[: self.config.max_tool_result_chars] + "...[truncated]"

    @staticmethod
    def _message_payload(message: Any) -> dict[str, str]:
        role = str(getattr(message, "role", "user"))
        if role not in {"system", "user", "assistant", "tool"}:
            role = "user"
        return {"role": role, "content": str(getattr(message, "content", ""))}


class BasicContextCompressor:
    """Rule-based context compressor for long sessions."""

    def __init__(self, config: ContextConfig | None = None) -> None:
        self.config = config or ContextConfig()

    def should_compress(self, session_state: Any) -> bool:
        """Return True when message count exceeds the configured threshold."""
        return len(getattr(session_state, "messages", [])) > self.config.compress_trigger_message_count

    def compress(self, session_state: Any) -> Any:
        """Compress older messages into summary and keep recent messages."""
        messages = list(getattr(session_state, "messages", []))
        keep_count = max(self.config.keep_recent_after_compress, 0)
        if keep_count == 0:
            old_messages = messages
            recent_messages = []
        else:
            old_messages = messages[:-keep_count]
            recent_messages = messages[-keep_count:]

        if not old_messages:
            return session_state

        summary = self._build_summary(session_state, old_messages)
        session_state.summary = summary
        session_state.messages = recent_messages
        return session_state

    def _build_summary(self, session_state: Any, old_messages: list[Any]) -> str:
        existing_summary = str(getattr(session_state, "summary", "")).strip()
        user_messages = [
            str(getattr(message, "content", ""))
            for message in old_messages
            if getattr(message, "role", "") == "user"
        ]
        assistant_messages = [
            str(getattr(message, "content", ""))
            for message in old_messages
            if getattr(message, "role", "") == "assistant"
        ]
        tool_results = list(getattr(session_state, "tool_results", []))[-self.config.recent_tool_result_limit :]
        todos = list(getattr(session_state, "todos", []))

        sections = []
        if existing_summary:
            sections.append("Previous summary:\n" + existing_summary)

        sections.extend(
            [
                "User goals:\n" + _compact_lines(user_messages[-5:]),
                "Completed items:\n" + _completed_todos(todos),
                "Open items:\n" + _open_todos(todos),
                "Important tool results:\n" + _compact_tool_results(tool_results),
                "User preferences and constraints:\n"
                + _extract_constraints(user_messages + assistant_messages),
            ]
        )
        return "\n\n".join(sections).strip()


def estimate_context_size(text_or_messages: Any) -> int:
    """Estimate context size using character count."""
    if isinstance(text_or_messages, str):
        return len(text_or_messages)
    return len(_to_json(_make_json_safe(text_or_messages)))


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


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
    return str(value)


def _compact_lines(lines: list[str]) -> str:
    useful_lines = [line.strip() for line in lines if line.strip()]
    if not useful_lines:
        return "- None captured yet."
    return "\n".join(f"- {line}" for line in useful_lines)


def _completed_todos(todos: list[dict[str, Any]]) -> str:
    completed = [str(todo.get("text", "")) for todo in todos if todo.get("done")]
    return _compact_lines(completed)


def _open_todos(todos: list[dict[str, Any]]) -> str:
    open_items = [str(todo.get("text", "")) for todo in todos if not todo.get("done")]
    return _compact_lines(open_items)


def _compact_tool_results(tool_results: list[Any]) -> str:
    if not tool_results:
        return "- None captured yet."
    lines = []
    for tool_result in tool_results:
        tool_name = getattr(tool_result, "tool_name", "")
        result = _to_json(_make_json_safe(getattr(tool_result, "result", None)))
        lines.append(f"- {tool_name}: {result[:300]}")
    return "\n".join(lines)


def _extract_constraints(lines: list[str]) -> str:
    keywords = ("must", "should", "不要", "需要", "必须", "prefer", "constraint", "要求")
    matches = [
        line.strip()
        for line in lines
        if line.strip() and any(keyword in line.casefold() for keyword in keywords)
    ]
    return _compact_lines(matches[-5:])
