# Mini Agent Runtime

[English](README.en.md) | [中文](README.zh-CN.md)

从零实现的最小可用 Agent Runtime，不依赖 LangGraph / OpenHands / OpenClaw 等现有 Agent 框架完成主流程。

核心能力：

- OpenAI-compatible 真实 LLM API
- Tool Schema 注册机制
- calculator / weather / todo / search 工具
- Agent Runtime loop
- `user_id + session_id` 级 session 隔离
- context 压缩
- trace 执行日志
- FakeLLM 测试
- pytest 104 passed

## 已实现功能

- 自定义 `ToolRegistry`
- 内置工具：calculator、search、weather、todo
- calculator 使用 Python AST 白名单解析，不直接使用 `eval`
- 用于解析 JSON LLM Action 的 Parser
- 基于 `user_id + session_id` 的 JSON session 持久化
- JSONL trace 日志
- ContextBuilder 和基础 context 压缩
- 核心 `AgentRuntime` 主循环
- OpenAI-compatible LLM Client
- 支持 real / fake 模式的 CLI demo

## 项目结构

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

## 安装

```bash
python -m pip install -r requirements.txt
```

或者：

```bash
python -m pip install -e ".[dev]"
```

## LLM 配置

CLI 启动时会自动读取当前工作目录下的 `.env` 文件，然后真实 LLM Client 从环境变量中读取配置：

```text
LLM_PROVIDER
LLM_API_KEY
LLM_MODEL
LLM_BASE_URL
LLM_TEMPERATURE
LLM_TIMEOUT_SECONDS
```

`LLM_PROVIDER` 当前支持 `openai_compatible`。`LLM_BASE_URL` 可选，默认是 `https://api.openai.com/v1`。`LLM_TEMPERATURE` 可选，默认是 `0`。`LLM_TIMEOUT_SECONDS` 可选，默认是 `60`。

可以复制 `.env.example` 为 `.env`，然后填写自己的 provider 配置。不要提交真实 API key。

PowerShell 示例：

```powershell
$env:LLM_PROVIDER="openai_compatible"
$env:LLM_API_KEY="your-api-key"
$env:LLM_MODEL="your-model-name"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_TEMPERATURE="0"
```

## CLI

推荐的 Windows / Anaconda 运行方式：

```powershell
D:\Anaconda\python.exe -m agent.cli --user alice --session window_1
```

兼容入口：

```powershell
python main.py --user alice --session window_1 --llm real
```

安装后的命令行入口：

```bash
mini-agent-runtime --user user_a --session window_1
```

离线 fake 模式：

```bash
python main.py --user user_a --session window_1 --llm fake
```

录屏 verbose 模式：

```bash
python main.py --user user_a --session window_1 --llm real --verbose
```

旧的 `--fake` 参数仍然可用，等价于 `--llm fake`。

进入交互式提示后，每次输入一行。输入 `exit` 或 `quit` 退出。

CLI 会自动注册 calculator、search、weather、todo 四个工具。默认情况下，session 和 trace 会写到 `data/` 目录。

## Runtime 行为

每一轮用户输入中，Runtime 会：

1. 加载 session 状态。
2. 保存当前 user message。
3. 基于 summary、todos、recent messages、recent tool results 和 tool schemas 构建 context。
4. 调用注入的 LLM client。
5. 将模型输出解析为 JSON Action。
6. 通过 registry 执行工具调用，或者返回最终答案。
7. 保存 messages、tool results、session state 和 trace events。

模型必须输出 JSON：

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

或者：

```json
{
  "type": "final",
  "reason": "short decision note",
  "answer": "The result is 391."
}
```

`reason` 只是简短调试说明，不是 chain-of-thought 字段。

本项目没有把核心流程交给 provider-side function calling。当前实现是：把工具 schema 注入 context，约束模型输出本地 JSON 协议，本地 Parser 解析，再由自研 Runtime 执行工具。

## 测试

```bash
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

普通 pytest 不会调用外部 LLM API。LLM 和 CLI 行为使用 fake 或 mock client 测试。

## Demo 辅助脚本

```powershell
python scripts/show_trace.py --user demo_user --session real_window --limit 20
python scripts/show_session.py --user demo_user --session real_window
python scripts/demo_compress.py --user demo_user --session compress_window
```

## 当前边界

- search 和 weather 是 mock 工具，不调用真实外部 API。
- 没有向量数据库或 RAG 框架。
- JSON session 和 trace 文件没有跨进程写锁。
- todo 在 `AgentRuntime` 内部已经做到 session-aware，后续可以抽象成通用 `ToolContext`。
- OpenAI-compatible client 只返回模型原始文本；解析和工具执行仍由本地 Runtime 完成。
