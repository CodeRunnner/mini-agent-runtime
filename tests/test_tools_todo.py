from __future__ import annotations

from tools.todo import TodoTool


def test_todo_add_list_done_flow() -> None:
    tool = TodoTool()

    add_result = tool.execute({"action": "add", "text": "Write tests"})
    assert add_result == {
        "ok": True,
        "item": {"id": 1, "text": "Write tests", "done": False},
    }

    list_result = tool.execute({"action": "list"})
    assert list_result == {
        "ok": True,
        "items": [{"id": 1, "text": "Write tests", "done": False}],
    }

    done_result = tool.execute({"action": "done", "id": 1})
    assert done_result == {
        "ok": True,
        "item": {"id": 1, "text": "Write tests", "done": True},
    }

    final_list = tool.execute({"action": "list"})
    assert final_list == {
        "ok": True,
        "items": [{"id": 1, "text": "Write tests", "done": True}],
    }


def test_todo_rejects_missing_text_for_add() -> None:
    result = TodoTool().execute({"action": "add"})

    assert result["ok"] is False
    assert result["error"] == "text must be a non-empty string"


def test_todo_rejects_unknown_done_id() -> None:
    result = TodoTool().execute({"action": "done", "id": 99})

    assert result["ok"] is False
    assert result["error"] == "todo item not found: 99"
