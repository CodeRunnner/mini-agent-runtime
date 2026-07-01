from __future__ import annotations

from agent.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from tools.todo import TodoTool
from tools.weather import WeatherTool


def test_builtin_tools_register_with_tool_registry() -> None:
    registry = ToolRegistry()
    tools = [CalculatorTool(), SearchTool(), WeatherTool(), TodoTool()]

    for tool in tools:
        registry.register(tool)

    assert registry.get("calculator") is tools[0]
    assert registry.get("search") is tools[1]
    assert registry.get("weather") is tools[2]
    assert registry.get("todo") is tools[3]


def test_builtin_tool_schemas_are_exported() -> None:
    registry = ToolRegistry()
    for tool in [CalculatorTool(), SearchTool(), WeatherTool(), TodoTool()]:
        registry.register(tool)

    schemas = registry.schemas()
    schema_names = {schema["name"] for schema in schemas}

    assert schema_names == {"calculator", "search", "weather", "todo"}
    assert all("description" in schema for schema in schemas)
    assert all("parameters" in schema for schema in schemas)
    assert all("execute" not in schema for schema in schemas)
