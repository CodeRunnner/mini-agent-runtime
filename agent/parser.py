"""Parse LLM output into structured runtime actions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any


TODO_ACTIONS = {"add", "list", "done"}


class ParseError(ValueError):
    """Raised when an LLM response cannot be parsed into an action."""


@dataclass(frozen=True)
class AgentAction:
    """Base structure for parsed runtime actions."""

    type: str
    reason: str = ""


@dataclass(frozen=True)
class ToolCallAction(AgentAction):
    """Action instructing the runtime to call a tool."""

    type: str = "tool_call"
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalAnswerAction(AgentAction):
    """Action instructing the runtime to return a final answer."""

    type: str = "final"
    answer: str = ""


def parse_llm_output(raw: str, tool_names: Iterable[str] | None = None) -> AgentAction:
    """Parse raw LLM output into a structured action."""
    data = _extract_first_json_object(raw)
    action_type = data.get("type")
    reason = _parse_reason(data)
    known_tool_names = {str(name) for name in tool_names or ()}

    if action_type == "tool_call":
        tool_name = data.get("tool_name")
        arguments = data.get("arguments")

        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ParseError("tool_call action requires a non-empty tool_name")
        if not isinstance(arguments, dict):
            raise ParseError("tool_call action requires arguments to be an object")

        return ToolCallAction(reason=reason, tool_name=tool_name, arguments=arguments)

    if isinstance(action_type, str) and action_type in known_tool_names:
        arguments = {
            key: value
            for key, value in data.items()
            if key not in {"type", "reason"}
        }
        return ToolCallAction(reason=reason, tool_name=action_type, arguments=arguments)

    if action_type == "final":
        answer = data.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ParseError("final action requires a non-empty answer")

        return FinalAnswerAction(reason=reason, answer=answer)

    if action_type is None:
        inferred_todo_action = data.get("action")
        if isinstance(inferred_todo_action, str) and inferred_todo_action in TODO_ACTIONS:
            return ToolCallAction(reason=reason, tool_name="todo", arguments=data)
        raise ParseError("action requires a type field")
    raise ParseError(f"unknown action type: {action_type}")


def _parse_reason(data: dict[str, Any]) -> str:
    reason = data.get("reason", "")
    if not isinstance(reason, str):
        raise ParseError("reason must be a string when provided")
    return reason


def _extract_first_json_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        raise ParseError("LLM output must be a non-empty string")

    decoder = json.JSONDecoder()
    for start in _json_object_start_positions(raw):
        try:
            value, _ = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            return value

    raise ParseError("could not parse a JSON object from LLM output")


def _json_object_start_positions(raw: str) -> list[int]:
    stripped = raw.lstrip()
    offset = len(raw) - len(stripped)
    positions: list[int] = []

    if stripped.startswith("{"):
        positions.append(offset)

    positions.extend(index for index, char in enumerate(raw) if char == "{" and index not in positions)
    return positions


class ResponseParser:
    """Compatibility wrapper for future runtime integration."""

    def parse(
        self, response: str, tool_names: Iterable[str] | None = None
    ) -> AgentAction:
        """Parse a model response into a runtime action."""
        return parse_llm_output(response, tool_names=tool_names)
