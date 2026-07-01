# Mini Agent Runtime

[中文](README.md) | [English](README.en.md)

`mini-agent-runtime` is a minimal usable Agent Runtime implemented from scratch.
It does not rely on LangGraph / OpenHands / OpenClaw or other existing Agent frameworks to run the core flow.

Core abilities:

- OpenAI-compatible real LLM API
- Tool Schema registry
- calculator / weather / todo / search tools
- Agent Runtime loop
- `user_id + session_id` session isolation
- context compression
- trace execution logs
- FakeLLM tests
- pytest 104 passed

## What Is Implemented

- Custom `ToolRegistry`
- Built-in tools: calculator, search, weather, todo
- Safe calculator using Python AST instead of `eval`
- Parser for JSON LLM actions
- JSON session persistence by `user_id + session_id`
- JSONL trace logging
- Context builder and basic context compression
- Core `AgentRuntime` loop
- OpenAI-compatible LLM client
- CLI demo with real and fake modes

## Project Layout

```text
agent/
  cli.py
  context.py
  llm_client.py
  parser.py
  runtime.py
  session.py
  tool_registry.py
  trace.py
tools/
  calculator.py
  search.py
  todo.py
  weather.py
tests/
```

## Install

```bash
python -m pip install -r requirements.txt
```

or:

```bash
python -m pip install -e ".[dev]"
```

## LLM Configuration

The CLI automatically loads a `.env` file from the current working directory,
then the real client reads configuration from environment variables:

```text
LLM_PROVIDER
LLM_API_KEY
LLM_MODEL
LLM_BASE_URL
LLM_TEMPERATURE
LLM_TIMEOUT_SECONDS
```

`LLM_PROVIDER` currently supports `openai_compatible`.
`LLM_BASE_URL` is optional and defaults to `https://api.openai.com/v1`.
`LLM_TEMPERATURE` is optional and defaults to `0`.
`LLM_TIMEOUT_SECONDS` is optional and defaults to `60`.

Copy `.env.example` to `.env` and fill in your provider values. Do not commit
real API keys.

PowerShell example:

```powershell
$env:LLM_PROVIDER="openai_compatible"
$env:LLM_API_KEY="your-api-key"
$env:LLM_MODEL="your-model-name"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_TEMPERATURE="0"
```

## CLI

Recommended Windows / Anaconda command:

```powershell
D:\Anaconda\python.exe -m agent.cli --user alice --session window_1
```

Compatibility entry point:

```powershell
python main.py --user alice --session window_1 --llm real
```

Installed console script:

```bash
mini-agent-runtime --user user_a --session window_1
```

Fake offline mode:

```bash
python main.py --user user_a --session window_1 --llm fake
```

Verbose demo mode:

```bash
python main.py --user user_a --session window_1 --llm real --verbose
```

The older `--fake` flag is still supported as an alias for `--llm fake`.

In the interactive prompt, enter one line at a time. Type `exit` or `quit` to stop.

The CLI registers calculator, search, weather, and todo automatically. Sessions and traces are stored under `data/` by default.

## Runtime Behavior

For each user turn, the runtime:

1. Loads session state.
2. Stores the user message.
3. Builds context from summary, todos, recent messages, recent tool results, and tool schemas.
4. Calls the injected LLM client.
5. Parses the model output as JSON.
6. Executes tool calls through the registry, or returns final answers.
7. Stores messages, tool results, session state, and trace events.

The model must output JSON:

```json
{
  "type": "tool_call",
  "reason": "short decision note",
  "tool_name": "calculator",
  "arguments": {
    "expression": "23*17"
  }
}
```

or:

```json
{
  "type": "final",
  "reason": "short decision note",
  "answer": "The result is 391."
}
```

`reason` is only a short debugging note. It is not a chain-of-thought field.

This project does not use provider-side function calling for the core flow.
Instead, it injects tool schemas into context, requires the model to output the
local JSON protocol above, parses that output locally, and executes tools in the
self-written runtime loop.

## Tests

```bash
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

The normal test suite does not call external LLM APIs. LLM and CLI behavior is tested with fake or mocked clients.

## Demo Helpers

```powershell
python scripts/show_trace.py --user demo_user --session real_window --limit 20
python scripts/show_session.py --user demo_user --session real_window
python scripts/demo_compress.py --user demo_user --session compress_window
```

## Current Boundaries

- No real web search or real weather API.
- No vector database or RAG framework.
- No cross-process file locking for JSON session or trace writes.
- Todo is session-aware inside `AgentRuntime`; later this should become a general `ToolContext`.
- OpenAI-compatible client returns raw model text only. Parsing and tool execution stay inside the local runtime.
