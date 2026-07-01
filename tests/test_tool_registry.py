from __future__ import annotations

from typing import Any

import pytest

from agent.tool_registry import ToolRegistry


class FakeTool:
    name = "fake"
    description = "A fake tool for tests."
    parameters = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
        },
        "required": ["value"],
    }

    def execute(self, arguments: dict[str, Any]) -> str:
        return str(arguments["value"])


def test_register_tool() -> None:
    registry = ToolRegistry()
    tool = FakeTool()

    registry.register(tool)

    assert registry.get("fake") is tool


def test_get_tool_by_name() -> None:
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)

    assert registry.get("fake") is tool


def test_register_duplicate_name_fails() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool())

    with pytest.raises(ValueError, match="Tool already registered: fake"):
        registry.register(FakeTool())


def test_get_missing_tool_fails() -> None:
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Tool not found: missing"):
        registry.get("missing")


def test_schema_export_contains_tool_metadata_only() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool())

    schemas = registry.schemas()

    assert schemas == [
        {
            "name": "fake",
            "description": "A fake tool for tests.",
            "parameters": FakeTool.parameters,
        }
    ]
    assert "execute" not in schemas[0]
