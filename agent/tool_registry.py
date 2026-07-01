"""Tool registration and schema export."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    """Protocol implemented by runtime tools."""

    name: str
    description: str
    parameters: dict[str, Any]

    def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool with validated arguments."""
        ...


class ToolRegistry:
    """Registry for tools available to the agent runtime."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by name."""
        self._validate_tool(tool)
        name = tool.name

        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")

        self._tools[name] = tool

    def get(self, name: str) -> Tool:
        """Return a registered tool by name."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not found: {name}") from exc

    def schemas(self) -> list[dict[str, Any]]:
        """Export tool schemas for model/tool selection."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": deepcopy(tool.parameters),
            }
            for tool in self._tools.values()
        ]

    @staticmethod
    def _validate_tool(tool: Tool) -> None:
        name = getattr(tool, "name", None)
        description = getattr(tool, "description", None)
        parameters = getattr(tool, "parameters", None)
        execute = getattr(tool, "execute", None)

        if not isinstance(name, str) or not name.strip():
            raise TypeError("Tool must define a non-empty string name.")
        if not isinstance(description, str) or not description.strip():
            raise TypeError("Tool must define a non-empty string description.")
        if not isinstance(parameters, dict):
            raise TypeError("Tool must define parameters as a JSON Schema dictionary.")
        if not callable(execute):
            raise TypeError("Tool must define an execute(arguments) method.")
