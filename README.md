# Mini Agent Runtime

从零实现的最小可用 Agent Runtime，不依赖 LangGraph / OpenHands / OpenClaw 等现有 Agent 框架完成主流程。

Choose a language / 选择语言：

- [中文](README.zh-CN.md)
- [English](README.en.md)

## Core Abilities

- OpenAI-compatible real LLM API
- Tool Schema registry
- calculator / weather / todo / search tools
- Agent Runtime loop
- `user_id + session_id` session isolation
- context compression
- trace execution logs
- FakeLLM tests
- pytest 104 passed

## Demo Video

- pytest 全量测试通过：104 passed
- 真实 LLM 调用 calculator 工具
- weather + todo 多工具连续调用
- session 隔离演示
- context 压缩演示
- trace 日志记录与展示
- GitHub Release: [Releases](https://github.com/CodeRunnner/mini-agent-runtime/releases)

## Quick Start

Install:

```powershell
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your OpenAI-compatible provider values.
Do not commit real API keys.

Run real LLM mode:

```powershell
python main.py --user alice --session window_1 --llm real --verbose
```

Run fake offline mode:

```powershell
python main.py --user alice --session window_1 --llm fake
```

Run tests:

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

## Documentation

- [Demo Script](docs/demo_script.md)
- [Architecture Answers](docs/architecture_answers.md)
- [AI Prompt Log](docs/ai_prompt_log.md)

## Current Boundaries

- search and weather are mock tools.
- JSON session and trace storage are local-file based.
- Context compression is rule based and intentionally lightweight.
- The runtime uses a local JSON action protocol instead of provider-side function calling.
