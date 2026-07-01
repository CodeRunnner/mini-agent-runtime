from __future__ import annotations

import json

import pytest

from agent.parser import FinalAnswerAction, ParseError, ToolCallAction, parse_llm_output


def test_parse_plain_json_tool_call() -> None:
    action = parse_llm_output(
        json.dumps(
            {
                "type": "tool_call",
                "reason": "Need arithmetic.",
                "tool_name": "calculator",
                "arguments": {"expression": "23*17"},
            }
        )
    )

    assert isinstance(action, ToolCallAction)
    assert action.type == "tool_call"
    assert action.reason == "Need arithmetic."
    assert action.tool_name == "calculator"
    assert action.arguments == {"expression": "23*17"}


def test_parse_plain_json_final_answer() -> None:
    action = parse_llm_output(
        json.dumps(
            {
                "type": "final",
                "reason": "Enough information.",
                "answer": "The result is 391.",
            }
        )
    )

    assert isinstance(action, FinalAnswerAction)
    assert action.type == "final"
    assert action.reason == "Enough information."
    assert action.answer == "The result is 391."


def test_parse_json_inside_markdown_code_block() -> None:
    action = parse_llm_output(
        """
```json
{
  "type": "tool_call",
  "reason": "Need a lookup.",
  "tool_name": "search",
  "arguments": {"query": "python agent"}
}
```
"""
    )

    assert isinstance(action, ToolCallAction)
    assert action.tool_name == "search"
    assert action.arguments == {"query": "python agent"}


def test_parse_first_json_object_from_text() -> None:
    action = parse_llm_output(
        """
I will use this action:
{
  "type": "final",
  "reason": "Ready to answer.",
  "answer": "Done."
}
Extra text after the action.
"""
    )

    assert isinstance(action, FinalAnswerAction)
    assert action.answer == "Done."


def test_invalid_json_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="could not parse"):
        parse_llm_output("not json at all")


def test_unknown_type_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="unknown action type"):
        parse_llm_output(json.dumps({"type": "other", "answer": "Nope."}))


def test_tool_call_missing_tool_name_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="tool_name"):
        parse_llm_output(
            json.dumps(
                {
                    "type": "tool_call",
                    "arguments": {"expression": "1 + 1"},
                }
            )
        )


def test_tool_call_arguments_must_be_dict() -> None:
    with pytest.raises(ParseError, match="arguments"):
        parse_llm_output(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "calculator",
                    "arguments": "expression=1+1",
                }
            )
        )


def test_final_missing_answer_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="answer"):
        parse_llm_output(json.dumps({"type": "final", "reason": "Missing answer."}))


def test_reason_defaults_to_empty_string() -> None:
    action = parse_llm_output(
        json.dumps(
            {
                "type": "tool_call",
                "tool_name": "calculator",
                "arguments": {"expression": "2 + 2"},
            }
        )
    )

    assert isinstance(action, ToolCallAction)
    assert action.reason == ""
