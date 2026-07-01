"""Offline mock search tool."""

from __future__ import annotations

from typing import Any


class SearchTool:
    name = "search"
    description = "Search for information using a query string."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."}
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any]) -> Any:
        """Search the built-in mock knowledge base."""
        query = arguments.get("query") if isinstance(arguments, dict) else None
        if not isinstance(query, str) or not query.strip():
            return {"ok": False, "error": "query must be a non-empty string", "results": []}

        normalized_query = query.casefold()
        results = [
            result
            for keyword, result in _MOCK_RESULTS.items()
            if keyword in normalized_query
            or normalized_query in keyword
            or normalized_query in result["title"].casefold()
            or normalized_query in result["snippet"].casefold()
        ]

        if not results:
            return {
                "ok": True,
                "query": query,
                "results": [],
                "message": "No mock search results found.",
            }

        return {"ok": True, "query": query, "results": results}


_MOCK_RESULTS = {
    "agent": {
        "title": "Agent Runtime",
        "snippet": "An agent runtime coordinates model responses, tools, and state.",
    },
    "python": {
        "title": "Python",
        "snippet": "Python is a general-purpose programming language used for automation and services.",
    },
    "weather": {
        "title": "Weather Tool",
        "snippet": "The weather tool returns deterministic mock forecasts for local testing.",
    },
    "todo": {
        "title": "Todo Tool",
        "snippet": "The todo tool manages short-lived tasks in memory during early development.",
    },
    "calculator": {
        "title": "Calculator Tool",
        "snippet": "The calculator safely evaluates arithmetic expressions using Python AST parsing.",
    },
}
