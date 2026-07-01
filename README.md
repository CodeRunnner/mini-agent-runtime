# Mini Agent Runtime

从零实现的最小可用 Agent Runtime，不依赖 LangGraph / OpenHands / OpenClaw 等现有 Agent 框架完成主流程。

语言版本：

- [中文说明](README.zh-CN.md)
- [English README](README.en.md)

## 核心能力

- OpenAI-compatible 真实 LLM API
- Tool Schema 注册机制
- calculator / weather / todo / search 工具
- Agent Runtime loop
- `user_id + session_id` 级 session 隔离
- context 压缩
- trace 执行日志
- FakeLLM 测试
- pytest 104 passed

## 演示视频

- pytest 全量测试通过：104 passed
- 真实 LLM 调用 calculator 工具
- weather + todo 多工具连续调用
- session 隔离演示
- context 压缩演示
- trace 日志记录与展示
- GitHub Release：[Releases](https://github.com/CodeRunnner/mini-agent-runtime/releases)

## 快速开始

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填写自己的 OpenAI-compatible provider 配置。不要提交真实 API key。

真实 LLM 模式：

```powershell
python main.py --user alice --session window_1 --llm real --verbose
```

离线 fake 模式：

```powershell
python main.py --user alice --session window_1 --llm fake
```

运行测试：

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

## 文档

- [架构设计回答](docs/architecture_answers.md)
- [AI 辅助开发记录](docs/ai_prompt_log.md)

## 当前边界

- search 和 weather 是 mock 工具。
- session 和 trace 使用本地 JSON / JSONL 文件保存。
- context 压缩是规则型基础实现。
- Runtime 使用本地 JSON action 协议，没有把核心流程交给 provider-side function calling。
