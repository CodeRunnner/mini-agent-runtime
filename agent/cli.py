"""Command line entry point for mini-agent-runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv

from agent.llm_client import FakeLLMClient, LLMClientError, OpenAICompatibleLLMClient
from agent.runtime import AgentRuntime, RuntimeConfig
from agent.session import JsonSessionStore
from agent.tool_registry import ToolRegistry
from agent.trace import JsonTraceLogger, TraceEvent
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print compact trace events for each user turn.",
    )
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
            before_count = 0
            if args.verbose:
                before_count = len(
                    runtime.trace_logger.read_events(
                        user_id=args.user,
                        session_id=args.session,
                    )
                )
            answer = runtime.run_turn(args.user, args.session, user_input)
        except Exception as exc:
            print(f"Runtime error: {exc}", file=sys.stderr)
            continue

        if args.verbose:
            events = runtime.trace_logger.read_events(
                user_id=args.user,
                session_id=args.session,
            )
            _print_verbose_events(events[before_count:])
        else:
            print(answer)


def _print_verbose_events(events: list[TraceEvent]) -> None:
    for event in events:
        line = _format_verbose_event(event)
        if line:
            print(line)


def _format_verbose_event(event: TraceEvent) -> str | None:
    payload = event.payload if isinstance(event.payload, dict) else {}
    if event.event_type == "tool_call":
        tool_name = str(payload.get("tool_name", ""))
        arguments = _compact_json(payload.get("arguments", {}))
        return f"[agent] tool_call: {tool_name} {arguments}"
    if event.event_type == "tool_result":
        tool_name = str(payload.get("tool_name", ""))
        result = _compact_json(payload.get("result"))
        return f"[tool] {tool_name} result: {result}"
    if event.event_type == "fallback_final":
        answer = _unwrap_answer_text(payload.get("raw_output", ""))
        return f"[agent] final(fallback): {answer}"
    if event.event_type == "final_answer":
        answer = _unwrap_answer_text(payload.get("answer", ""))
        return f"[agent] final: {answer}"
    if event.event_type == "error":
        return f"[error] {event.error}"
    return None


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _unwrap_answer_text(value: Any) -> str:
    if isinstance(value, dict) and "answer" in value:
        return str(value["answer"])
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, dict) and "answer" in parsed:
            return str(parsed["answer"])
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
