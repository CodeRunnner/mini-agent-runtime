from __future__ import annotations

from tools.search import SearchTool


def test_search_returns_matching_results() -> None:
    result = SearchTool().execute({"query": "python agent"})

    assert result["ok"] is True
    assert result["query"] == "python agent"
    assert {item["title"] for item in result["results"]} >= {"Python", "Agent Runtime"}


def test_search_returns_empty_results_for_miss() -> None:
    result = SearchTool().execute({"query": "nonexistent keyword"})

    assert result["ok"] is True
    assert result["results"] == []
    assert result["message"] == "No mock search results found."
