# Mini Agent Runtime

从零实现的最小可用 Agent Runtime，不依赖 LangGraph / OpenHands / OpenClaw 等现有 Agent 框架完成主流程。

Choose a language / 选择语言：

- [中文](README.zh-CN.md)
- [English](README.en.md)

## 核心能力

- OpenAI-compatible 真实 LLM API
- Tool Schema 注册机制
- calculator / weather / todo / search 工具
- Agent Runtime loop
- `user_id + session_id` 级 session 隔离
- context 压缩
- trace 执行日志
- FakeLLM 测试
- pytest 97 passed

## Core Abilities

- OpenAI-compatible real LLM API
- Tool Schema registry
- calculator / weather / todo / search tools
- Agent Runtime loop
- `user_id + session_id` session isolation
- context compression
- trace execution logs
- FakeLLM tests
- pytest 97 passed
