"""Core agent runtime loop."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agent.context import AgentContext, BasicContextCompressor, ContextBuilder
from agent.llm_client import FakeLLMClient, LLMClient
from agent.parser import FinalAnswerAction, ParseError, ResponseParser, ToolCallAction
from agent.session import JsonSessionStore, SessionState
from agent.tool_registry import ToolRegistry
from agent.trace import JsonTraceLogger, TraceEvent


class AgentRuntimeError(Exception):
    """Base exception for controlled runtime failures."""


class MaxStepsExceeded(AgentRuntimeError):
    """Raised internally when the runtime exceeds max_steps."""


@dataclass
class RuntimeConfig:
    """Runtime execution settings."""

    max_steps: int = 5


class AgentRuntime:
    """Small self-contained agent runtime loop."""

    def __init__(
        self,
        llm_client: Any | None = None,
        parser: ResponseParser | None = None,
        tool_registry: ToolRegistry | None = None,
        session_store: JsonSessionStore | None = None,
        trace_logger: JsonTraceLogger | None = None,
        context_builder: ContextBuilder | None = None,
        context_compressor: BasicContextCompressor | None = None,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.parser = parser or ResponseParser()
        self.tool_registry = tool_registry or ToolRegistry()
        self.session_store = session_store or JsonSessionStore()
        self.trace_logger = trace_logger or JsonTraceLogger()
        self.context_builder = context_builder or ContextBuilder()
        self.context_compressor = context_compressor or BasicContextCompressor()
        self.config = config or RuntimeConfig()

    def run(self, context: AgentContext) -> str:
        """Legacy compatibility entry point; use run_turn for session-aware execution."""
        raise NotImplementedError("Use run_turn(user_id, session_id, user_input).")

    def run_turn(self, user_id: str, session_id: str, user_input: str) -> str:
        """Run one user turn until final answer, parse error, or max_steps."""
        session_state = self.session_store.load(user_id, session_id)
        session_state = self.session_store.append_message(
            user_id, session_id, "user", user_input
        )
        self.trace_logger.log_event(
            TraceEvent(
                user_id=user_id,
                session_id=session_id,
                step=0,
                event_type="user_message",
                payload={"content": user_input},
            )
        )

        if self.context_compressor.should_compress(session_state):
            session_state = self.context_compressor.compress(session_state)
            self.session_store.save(session_state)

        tool_schemas = self.tool_registry.schemas()
        for step in range(1, self.config.max_steps + 1):
            messages = self.context_builder.build_messages(session_state, tool_schemas)

            llm_started = perf_counter()
            raw_output = self.llm_client.complete(messages)
            llm_duration_ms = _elapsed_ms(llm_started)
            self.trace_logger.log_llm_output(
                user_id, session_id, step, raw_output, duration_ms=llm_duration_ms
            )

            parse_started = perf_counter()
            try:
                action = self.parser.parse(raw_output)
            except ParseError as exc:
                error_message = f"Runtime error: failed to parse LLM output: {exc}"
                self.trace_logger.log_error(
                    user_id,
                    session_id,
                    step,
                    exc,
                    payload={"raw_output": raw_output},
                )
                self.session_store.append_message(
                    user_id, session_id, "assistant", error_message
                )
                return error_message

            self.trace_logger.log_parse_action(
                user_id,
                session_id,
                step,
                action,
                duration_ms=_elapsed_ms(parse_started),
            )

            if isinstance(action, FinalAnswerAction):
                session_state = self.session_store.append_message(
                    user_id, session_id, "assistant", action.answer
                )
                self.trace_logger.log_final_answer(user_id, session_id, step, action.answer)
                self.session_store.save(session_state)
                return action.answer

            if isinstance(action, ToolCallAction):
                self.trace_logger.log_tool_call(
                    user_id, session_id, step, action.tool_name, action.arguments
                )
                result = self._run_tool_action(user_id, session_id, step, action, session_state)
                session_state = self.session_store.load(user_id, session_id)
                self.session_store.save(session_state)
                if _is_error_result(result):
                    continue
                continue

            error_message = f"Runtime error: unsupported action: {type(action).__name__}"
            self.trace_logger.log_error(user_id, session_id, step, error_message)
            self.session_store.append_message(user_id, session_id, "assistant", error_message)
            return error_message

        error_message = f"Runtime error: max steps exceeded ({self.config.max_steps})"
        self.trace_logger.log_error(
            user_id,
            session_id,
            self.config.max_steps,
            MaxStepsExceeded(error_message),
        )
        self.session_store.append_message(user_id, session_id, "assistant", error_message)
        return error_message

    def _run_tool_action(
        self,
        user_id: str,
        session_id: str,
        step: int,
        action: ToolCallAction,
        session_state: SessionState,
    ) -> Any:
        tool_started = perf_counter()
        try:
            result = self._execute_tool(action.tool_name, action.arguments, session_state)
        except KeyError as exc:
            result = {"ok": False, "error": f"tool not found: {action.tool_name}"}
            self.trace_logger.log_error(
                user_id,
                session_id,
                step,
                exc,
                payload={"tool_name": action.tool_name, "arguments": action.arguments},
            )
        except Exception as exc:  # pragma: no cover - covered by behavior tests
            result = {"ok": False, "error": f"tool execution failed: {exc}"}
            self.trace_logger.log_error(
                user_id,
                session_id,
                step,
                exc,
                payload={"tool_name": action.tool_name, "arguments": action.arguments},
            )

        duration_ms = _elapsed_ms(tool_started)
        self.trace_logger.log_tool_result(
            user_id, session_id, step, action.tool_name, result, duration_ms=duration_ms
        )

        self.session_store.save(session_state)
        session_state = self.session_store.append_tool_result(
            user_id, session_id, action.tool_name, action.arguments, result
        )
        self.session_store.append_message(
            user_id,
            session_id,
            "tool",
            json.dumps(
                {
                    "tool_name": action.tool_name,
                    "arguments": action.arguments,
                    "result": result,
                },
                ensure_ascii=False,
                default=str,
            ),
            metadata={"tool_name": action.tool_name},
        )
        return result

    def _execute_tool(
        self, tool_name: str, arguments: dict[str, Any], session_state: SessionState
    ) -> Any:
        """Execute a tool.

        The todo branch is an MVP session-aware adapter. Later, this should be
        generalized into a ToolContext passed to tools that need session state.
        """
        if tool_name == "todo":
            return self._execute_session_todo(arguments, session_state)

        tool = self.tool_registry.get(tool_name)
        return tool.execute(arguments)

    @staticmethod
    def _execute_session_todo(arguments: dict[str, Any], session_state: SessionState) -> Any:
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "arguments must be an object"}

        action = arguments.get("action")
        if not isinstance(action, str):
            return {"ok": False, "error": "action must be a string"}

        action = action.casefold().strip()
        if action == "add":
            text = arguments.get("text")
            if not isinstance(text, str) or not text.strip():
                return {"ok": False, "error": "text must be a non-empty string"}

            next_id = max((int(item.get("id", 0)) for item in session_state.todos), default=0) + 1
            item = {"id": next_id, "text": text.strip(), "done": False}
            session_state.todos.append(item)
            return {"ok": True, "item": deepcopy(item)}

        if action == "list":
            return {"ok": True, "items": deepcopy(session_state.todos)}

        if action == "done":
            try:
                target_id = int(arguments.get("id"))
            except (TypeError, ValueError):
                return {"ok": False, "error": "id must be an integer"}

            for item in session_state.todos:
                if item.get("id") == target_id:
                    item["done"] = True
                    return {"ok": True, "item": deepcopy(item)}
            return {"ok": False, "error": f"todo item not found: {target_id}"}

        return {"ok": False, "error": f"unsupported action: {action}"}


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _is_error_result(result: Any) -> bool:
    return isinstance(result, dict) and result.get("ok") is False
