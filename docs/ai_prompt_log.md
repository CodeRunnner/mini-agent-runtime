# AI Prompt Log

This project was developed with AI assistance, but the runtime architecture and acceptance boundaries were reviewed and confirmed by me.

## Development Flow

1. Project skeleton
   - Used AI to scaffold the Python package layout, CLI entry point, README, and initial tests.
   - Confirmed the project would not use prebuilt agent frameworks.

2. ToolRegistry
   - Used AI to implement a small registry with `register`, `get`, and schema export.
   - Confirmed the tool interface: `name`, `description`, `parameters`, and `execute(arguments)`.

3. Built-in tools
   - Used AI to implement calculator, search, weather, and todo.
   - Reviewed calculator safety and confirmed it uses AST whitelist parsing instead of direct `eval`.
   - Confirmed tool outputs are structured dictionaries with `ok`, `result`, or `error`.

4. Parser
   - Used AI to implement JSON action parsing for `tool_call` and `final`.
   - Confirmed the Parser only converts raw model text into structured actions.
   - Confirmed the Parser does not execute tools, access the registry, or guess user intent.

5. SessionStore
   - Used AI to implement `SessionState` and local JSON persistence.
   - Confirmed state isolation by `user_id + session_id`.
   - Confirmed dangerous path characters are sanitized before writing files.

6. TraceLogger
   - Used AI to implement append-only JSONL trace logging.
   - Confirmed trace events include LLM output, parse action, tool calls, tool results, final answers, and errors.

7. ContextBuilder
   - Used AI to implement context construction from system prompt, tool schemas, summary, todos, recent messages, and recent tool results.
   - Confirmed context excludes full trace data.
   - Confirmed prompt constraints require JSON output and only allow a short `reason`, not full reasoning text.

8. Runtime
   - Used AI to implement the local Agent Runtime loop.
   - Confirmed the loop is implemented directly in this project: load session, build context, call LLM, parse action, execute tools, save state, and write trace.
   - Confirmed `max_steps` prevents infinite loops.
   - Confirmed todo is session-aware in Runtime as an MVP adapter.

9. LLMClient and CLI
   - Used AI to implement an OpenAI-compatible client and interactive CLI.
   - Confirmed API keys are read from environment variables, not committed or printed.
   - Confirmed tests use fake or mocked clients and do not call external APIs.

10. Test and fix cycle
    - Used AI to generate and run pytest coverage after each module.
    - Reviewed failures and accepted fixes only when they preserved the intended module boundaries.

## My Confirmation

- AI assisted with implementation, test generation, and debugging.
- I confirmed the module boundaries, safety tradeoffs, and MVP scope.
- I confirmed the final verification command and reviewed remaining limitations.
- The project is intentionally small and transparent: no hidden framework loop, no external orchestration framework, and no real API calls in tests.
