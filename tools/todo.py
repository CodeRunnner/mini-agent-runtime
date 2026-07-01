"""In-memory todo tool."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class TodoTool:
    name = "todo"
    description = "Manage a simple todo item."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Todo action to perform.",
                "enum": ["add", "list", "done"],
            },
            "id": {"type": "integer", "description": "Todo item id for done action."},
            "text": {"type": "string", "description": "Todo item text."},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self) -> None:
        # TODO: Move this storage into session state so different sessions get isolated todos.
        self._items: list[dict[str, Any]] = []
        self._next_id = 1

    def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute a todo action."""
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "arguments must be an object"}

        action = arguments.get("action")
        if not isinstance(action, str):
            return {"ok": False, "error": "action must be a string"}

        action = action.casefold().strip()
        if action == "add":
            return self._add(arguments.get("text"))
        if action == "list":
            return {"ok": True, "items": deepcopy(self._items)}
        if action == "done":
            return self._done(arguments.get("id"))

        return {"ok": False, "error": f"unsupported action: {action}"}

    def _add(self, text: Any) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return {"ok": False, "error": "text must be a non-empty string"}

        item = {"id": self._next_id, "text": text.strip(), "done": False}
        self._next_id += 1
        self._items.append(item)
        return {"ok": True, "item": deepcopy(item)}

    def _done(self, item_id: Any) -> dict[str, Any]:
        try:
            target_id = int(item_id)
        except (TypeError, ValueError):
            return {"ok": False, "error": "id must be an integer"}

        for item in self._items:
            if item["id"] == target_id:
                item["done"] = True
                return {"ok": True, "item": deepcopy(item)}

        return {"ok": False, "error": f"todo item not found: {target_id}"}
