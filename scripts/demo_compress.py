"""Create a small context compression demo session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from agent.context import BasicContextCompressor, ContextConfig
from agent.session import JsonSessionStore, Message


def run_demo(
    data_dir: str | Path,
    user_id: str,
    session_id: str,
    *,
    message_count: int = 25,
) -> dict[str, object]:
    """Seed a session and run the rule-based compressor."""
    store = JsonSessionStore(Path(data_dir) / "sessions")
    state = store.load(user_id, session_id)

    if len(state.messages) < message_count:
        for index in range(len(state.messages), message_count):
            state.messages.append(
                Message(
                    role="user",
                    content=f"Demo message {index}: keep the runtime small and transparent.",
                )
            )
        store.save(state)

    compressor = BasicContextCompressor(
        ContextConfig(compress_trigger_message_count=20, keep_recent_after_compress=8)
    )
    before_messages = len(state.messages)
    compressed = compressor.should_compress(state)
    if compressed:
        compressor.compress(state)
        store.save(state)

    return {
        "user_id": user_id,
        "session_id": session_id,
        "compressed": compressed,
        "before_messages": before_messages,
        "after_messages": len(state.messages),
        "summary_chars": len(state.summary),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the context compression demo."""
    parser = argparse.ArgumentParser(description="Demo mini-agent-runtime context compression.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--user", default="demo_user", dest="user_id")
    parser.add_argument("--session", default="compress_window", dest="session_id")
    parser.add_argument("--message-count", type=int, default=25)
    args = parser.parse_args(argv)

    result = run_demo(
        args.data_dir,
        args.user_id,
        args.session_id,
        message_count=args.message_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
