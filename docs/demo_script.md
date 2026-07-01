# Demo Script

This script is for recording or live-demoing the MVP submission.

## 1. Fake Mode Smoke Demo

Run:

```powershell
cd D:\myproject\mini-agent-runtime
D:\Anaconda\python.exe -m pip install -r requirements.txt
python main.py --user demo_user --session fake_window --llm fake
```

Type:

```text
hello
quit
```

Say:

- This is the offline CLI smoke path.
- The CLI constructs the real local `AgentRuntime`, registers the built-in tools, and uses a fake LLM response.
- No external API is called in fake mode.

## 2. Real LLM Mode Demo

Create `.env` from `.env.example` and fill in real values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Run:

```powershell
python main.py --user demo_user --session real_window --llm real --verbose
```

Try prompts such as:

```text
Calculate 23 * 17.
Add a todo item: review the runtime trace.
What todos do I have?
quit
```

Say:

- The real client calls an OpenAI-compatible chat completions endpoint.
- The CLI loads `.env` from the project root before constructing the client.
- The model must return JSON actions.
- The runtime parses those actions, executes local tools through `ToolRegistry`, stores session state, and writes trace events.
- `--verbose` prints compact tool calls, tool results, final answers, and errors without dumping full LLM output.
- The API key is read from environment variables and is never printed by the CLI.

## 3. Session Isolation Demo

Open two terminals.

Terminal A:

```powershell
python main.py --user demo_user --session window_1 --llm real --verbose
```

Terminal B:

```powershell
python main.py --user demo_user --session window_2 --llm real --verbose
```

Add different todo items in each session.

Say:

- Session state is keyed by `user_id + session_id`.
- `window_1` and `window_2` write separate JSON files under `data/sessions`.
- Todo is currently session-aware inside `AgentRuntime`; later it can be generalized through a `ToolContext`.

## 4. Trace File Demo

After a run, inspect:

```powershell
python scripts/show_trace.py --user demo_user --session real_window --limit 20
```

Expected event types include:

- `user_message`
- `llm_output`
- `parse_action`
- `tool_call`
- `tool_result`
- `final_answer`
- `error`

Say:

- The trace is JSONL, one event per line.
- Trace logging is observational and separate from session state.
- It is useful for debugging model output, parser decisions, tool execution, and failure handling.

## 5. Session File Demo

Inspect:

```powershell
python scripts/show_session.py --user demo_user --session real_window
```

Say:

- The session file contains user messages, assistant messages, tool messages, tool results, todos, summary, and timestamps.
- This is local JSON persistence for the MVP.
- It is not a production database or concurrent storage layer.

## 6. Test Demo

Run:

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

Say:

- The normal test suite does not call a real LLM.
- Runtime behavior is tested with fake or mocked clients.
- E2E tests cover calculator, todo, session isolation, trace, max steps, parser errors, and tool errors.

## 7. Context Compression Demo

Run:

```powershell
python scripts/demo_compress.py --user demo_user --session compress_window
python scripts/show_session.py --user demo_user --session compress_window
```

Say:

- Context compression is rule based in this MVP.
- It summarizes older messages, keeps recent messages, and preserves todos and tool results.
