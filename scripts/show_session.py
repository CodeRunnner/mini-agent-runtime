"""Display persisted session state for a user/session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from agent.session import JsonSessionStore, SessionState


def session_to_display(state: SessionState) -> dict[str, Any]:
    """Return a compact JSON-serializable session summary."""
    return {
        "user_id": state.user_id,
        "session_id": state.session_id,
        "status": state.status,
        "summary": state.summary,
        "message_count": len(state.messages),
        "tool_result_count": len(state.tool_results),
        "todos": state.todos,
        "recent_messages": [message.__dict__ for message in state.messages[-8:]],
        "tool_results": [tool_result.__dict__ for tool_result in state.tool_results],
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def load_existing_session(data_dir: str | Path, user_id: str, session_id: str) -> SessionState | None:
    """Load a session only if the JSON file already exists."""
    store = JsonSessionStore(Path(data_dir) / "sessions")
    path = store._session_path(user_id, session_id)
    if not path.exists():
        return None
    return store.load(user_id, session_id)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the session display script."""
    parser = argparse.ArgumentParser(description="Show mini-agent-runtime session state.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--user", required=True, dest="user_id")
    parser.add_argument("--session", required=True, dest="session_id")
    args = parser.parse_args(argv)

    state = load_existing_session(args.data_dir, args.user_id, args.session_id)
    if state is None:
        print(f"No session found for user={args.user_id} session={args.session_id}.")
        return 1

    print(json.dumps(session_to_display(state), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
