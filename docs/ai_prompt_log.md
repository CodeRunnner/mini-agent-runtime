# AI 辅助开发记录

本项目使用 AI 辅助完成实现、测试和排错，但 Runtime 架构边界、模块取舍、安全策略和最终验收由我确认。

## 开发过程

1. 项目骨架
   - 使用 AI 辅助创建 Python 包结构、CLI 入口、README 和初始测试。
   - 明确不使用 LangGraph、OpenHands、OpenClaw 等现成 Agent 框架接管主流程。

2. ToolRegistry
   - 使用 AI 辅助实现轻量工具注册表，支持 `register`、`get` 和 schema export。
   - 我确认工具接口统一为 `name`、`description`、`parameters`、`execute(arguments)`。

3. 内置工具
   - 使用 AI 辅助实现 calculator、search、weather、todo。
   - 我重点检查 calculator 安全边界，确认没有直接 `eval`，而是使用 AST 白名单解析。
   - 我确认工具输出使用结构化 dict，例如 `ok`、`result`、`error`。

4. Parser
   - 使用 AI 辅助实现 LLM JSON action 解析。
   - 我确认 Parser 只负责把 raw model output 转成 `ToolCallAction` 或 `FinalAnswerAction`。
   - Parser 不执行工具、不访问 ToolRegistry、不猜用户意图。

5. SessionStore
   - 使用 AI 辅助实现 `SessionState` 和本地 JSON 持久化。
   - 我确认 session 以 `user_id + session_id` 隔离。
   - 我确认 user_id/session_id 会做安全化处理，避免路径穿越。

6. TraceLogger
   - 使用 AI 辅助实现 JSONL trace 日志。
   - 我确认 trace 覆盖 LLM 输出、解析动作、工具调用、工具结果、最终答案和错误。

7. ContextBuilder
   - 使用 AI 辅助实现 context 构建和基础压缩。
   - 我确认 context 包含 system prompt、tool schemas、summary、todos、recent messages 和 recent tool results。
   - 我确认完整 trace 和完整 chain-of-thought 不进入 context。

8. AgentRuntime
   - 使用 AI 辅助实现核心 Runtime loop。
   - 我确认主循环由本项目自行实现：加载 session、构建 context、调用 LLM、解析 action、执行工具、保存状态、写 trace。
   - 我确认 `max_steps` 防止无限循环。
   - 我确认 todo 在 Runtime 中通过 MVP adapter 实现 session-aware 行为。

9. LLMClient 和 CLI
   - 使用 AI 辅助实现 OpenAI-compatible LLM client 和交互式 CLI。
   - 我确认 API key 只从环境变量或 `.env` 读取，不写入代码，不在 CLI 输出。
   - 我确认测试使用 FakeLLM 或 mock client，不在普通 pytest 中调用真实 LLM。

10. 真实 LLM demo 修复
    - 使用 AI 辅助补充 `--verbose`，让录屏时能看到 tool_call、tool_result、final_answer。
    - 使用 AI 辅助增加 `fallback_final`，处理工具执行后模型偶发返回短纯文本的情况。
    - 使用 AI 辅助增强 Parser，兼容真实模型偶发输出 `{"type":"todo",...}` 或 `{"action":"list"}` 的情况。
    - 我确认这些改动是兼容层，不改变 ToolRegistry、SessionStore、TraceLogger 的核心接口。

11. 测试和修复
    - 使用 AI 辅助补齐 pytest 覆盖。
    - 我根据失败用例检查边界，并只接受不破坏模块职责的修复。
    - 当前全量测试通过：`104 passed`。

## 我的确认

- AI 辅助了实现、测试生成和问题定位。
- 我确认了模块边界、安全取舍和 MVP 范围。
- 我确认核心 Agent Runtime 主流程由项目自行实现。
- 我确认项目没有把主流程交给现成 Agent 框架。
- 我确认真实 API key 不提交，`.env` 和 `data/` 已加入 `.gitignore`。
