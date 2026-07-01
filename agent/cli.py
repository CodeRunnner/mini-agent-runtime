"""Command line entry point for mini-agent-runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from agent.llm_client import FakeLLMClient, LLMClientError, OpenAICompatibleLLMClient
from agent.runtime import AgentRuntime, RuntimeConfig
from agent.session import JsonSessionStore
from agent.tool_registry import ToolRegistry
from agent.trace import JsonTraceLogger
from tools.calculator import CalculatorTool
from tools.search import SearchTool
from tools.todo import TodoTool
from tools.weather import WeatherTool


def build_tool_registry() -> ToolRegistry:
    """Register built-in tools for the CLI runtime."""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(WeatherTool())
    registry.register(TodoTool())
    return registry


def build_runtime(
    *,
    fake: bool = False,
    llm: str = "real",
    data_dir: str | Path = "data",
    max_steps: int = 5,
) -> AgentRuntime:
    """Build a CLI runtime with either real or fake LLM client."""
    mode = "fake" if fake else llm
    if mode not in {"real", "fake"}:
        raise ValueError("llm must be either 'real' or 'fake'.")

    if mode == "fake":
        llm_client = FakeLLMClient(
            [
                json.dumps(
                    {
                        "type": "final",
                        "reason": "Offline fake response.",
                        "answer": "Fake mode is running. Configure a real LLM to exercise tool loops.",
                    }
                )
            ],
            repeat_last=True,
        )
    else:
        llm_client = OpenAICompatibleLLMClient()

    data_path = Path(data_dir)
    return AgentRuntime(
        llm_client=llm_client,
        tool_registry=build_tool_registry(),
        session_store=JsonSessionStore(data_path / "sessions"),
        trace_logger=JsonTraceLogger(data_path / "traces" / "trace.jsonl"),
        config=RuntimeConfig(max_steps=max_steps),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the interactive CLI."""
    load_dotenv(Path.cwd() / ".env", override=False)

    parser = argparse.ArgumentParser(description="Run mini-agent-runtime.")
    parser.add_argument("--user", default="default_user", help="User id for session state.")
    parser.add_argument("--session", default="default_session", help="Session id for session state.")
    parser.add_argument(
        "--llm",
        choices=["real", "fake"],
        default="real",
        help="LLM mode. Use 'fake' for offline smoke demos.",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Compatibility alias for --llm fake.",
    )
    parser.add_argument("--data-dir", default="data", help="Directory for session and trace data.")
    parser.add_argument("--max-steps", type=int, default=5, help="Maximum runtime loop steps.")
    args = parser.parse_args(argv)

    try:
        mode = "fake" if args.fake else args.llm
        runtime = build_runtime(llm=mode, data_dir=args.data_dir, max_steps=args.max_steps)
    except LLMClientError as exc:
        print(f"LLM configuration error: {exc}", file=sys.stderr)
        return 1

    print(f"mini-agent-runtime started for user={args.user} session={args.session}")
    print("Type exit or quit to stop.")

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print()
            return 0

        if user_input.casefold() in {"exit", "quit"}:
            return 0
        if not user_input:
            continue

        try:
            answer = runtime.run_turn(args.user, args.session, user_input)
        except Exception as exc:
            print(f"Runtime error: {exc}", file=sys.stderr)
            continue

        print(answer)


if __name__ == "__main__":
    raise SystemExit(main())
