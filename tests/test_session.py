from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent.session import JsonSessionStore, Message, SessionState, ToolResult


def test_missing_session_is_created(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    state = store.load("user_1", "window_1")

    assert isinstance(state, SessionState)
    assert state.user_id == "user_1"
    assert state.session_id == "window_1"
    assert state.status == "idle"
    assert state.summary == ""
    assert state.messages == []
    assert state.todos == []
    assert state.tool_results == []
    assert datetime.fromisoformat(state.created_at).tzinfo is not None
    assert datetime.fromisoformat(state.updated_at).tzinfo is not None
    assert (tmp_path / "sessions" / "user_1" / "window_1.json").exists()


def test_sessions_for_same_user_are_isolated(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    store.append_message("user_1", "window_1", "user", "hello window 1")
    store.append_message("user_1", "window_2", "user", "hello window 2")

    window_1 = store.load("user_1", "window_1")
    window_2 = store.load("user_1", "window_2")

    assert [message.content for message in window_1.messages] == ["hello window 1"]
    assert [message.content for message in window_2.messages] == ["hello window 2"]


def test_same_session_id_for_different_users_is_isolated(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    store.append_message("alice", "main", "user", "from alice")
    store.append_message("bob", "main", "user", "from bob")

    alice = store.load("alice", "main")
    bob = store.load("bob", "main")

    assert [message.content for message in alice.messages] == ["from alice"]
    assert [message.content for message in bob.messages] == ["from bob"]


def test_append_message_persists_after_reload(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    state = store.append_message(
        "user_1",
        "main",
        "user",
        "calculate 23 * 17",
        metadata={"source": "cli"},
    )
    reloaded = store.load("user_1", "main")

    assert len(state.messages) == 1
    assert reloaded.messages == [
        Message(role="user", content="calculate 23 * 17", metadata={"source": "cli"}, created_at=reloaded.messages[0].created_at)
    ]


def test_append_tool_result_persists_after_reload(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    store.append_tool_result(
        "user_1",
        "main",
        "calculator",
        {"expression": "23*17"},
        {"ok": True, "result": 391},
    )
    reloaded = store.load("user_1", "main")

    assert reloaded.tool_results == [
        ToolResult(
            tool_name="calculator",
            arguments={"expression": "23*17"},
            result={"ok": True, "result": 391},
            created_at=reloaded.tool_results[0].created_at,
        )
    ]


def test_get_recent_messages_returns_recent_limit(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")
    for index in range(5):
        store.append_message("user_1", "main", "user", f"message {index}")

    recent = store.get_recent_messages("user_1", "main", limit=2)

    assert [message.content for message in recent] == ["message 3", "message 4"]


def test_update_summary_persists(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")

    store.update_summary("user_1", "main", "User is testing sessions.")
    reloaded = store.load("user_1", "main")

    assert reloaded.summary == "User is testing sessions."


def test_dangerous_ids_do_not_escape_base_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "sessions"
    store = JsonSessionStore(base_dir)

    state = store.load("../evil/user", "..\\session/../../x")

    assert state.user_id == "../evil/user"
    assert state.session_id == "..\\session/../../x"
    saved_files = list(base_dir.rglob("*.json"))
    assert len(saved_files) == 1
    assert saved_files[0].resolve().is_relative_to(base_dir.resolve())
    assert not (tmp_path / "evil").exists()


def test_saved_json_is_readable(tmp_path: Path) -> None:
    store = JsonSessionStore(tmp_path / "sessions")
    store.append_message("user_1", "main", "assistant", "hello")

    path = tmp_path / "sessions" / "user_1" / "main.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["user_id"] == "user_1"
    assert data["session_id"] == "main"
    assert data["messages"][0]["content"] == "hello"
