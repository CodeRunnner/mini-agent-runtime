# Architecture Answers

## 1. 200 轮对话如何管理 context？

项目不会把 200 轮完整消息无差别塞回 LLM。`JsonSessionStore` 会持久化完整 session 状态，`ContextBuilder` 只把当前轮真正需要的信息放入 LLM context：

- system prompt：约束模型只能输出本地 JSON action 协议。
- tool schemas：让模型知道当前可调用工具和参数格式。
- session summary：保存旧对话压缩后的稳定事实。
- structured state：例如当前 session 的 todos。
- recent messages：只保留最近 N 条消息，默认 8 条。
- recent tool results：只保留最近 N 个工具结果，默认 3 个。

当消息数量超过阈值时，`BasicContextCompressor` 会把较旧消息压缩进 `session_state.summary`，并保留最近消息。压缩是规则型 MVP 实现，不调用额外 LLM，也不引入向量数据库。这样 200 轮对话仍能保留用户目标、待办状态、重要工具结果和近期上下文，同时避免 context 无限增长。

## 2. memory 什么时候召回，放在 context 的什么位置？

本项目当前的 memory 主要是 session 级 memory，而不是全局长期记忆。召回时机是在每轮调用 LLM 前：Runtime 先 `load(user_id, session_id)` 取出 session state，然后由 `ContextBuilder.build_messages()` 构建上下文。

放入 context 的位置按重要性分层：

- system prompt 放在最前面，保证输出协议优先级最高。
- tool schemas 紧随其后，支持模型基于 schema 决策是否调用工具。
- session summary 放在 system 信息中，用于召回压缩后的长期上下文。
- structured state 放在 system 信息中，例如 todos，便于模型精确读取当前状态。
- recent tool results 和 recent messages 放在后面，支持追问和多步工具链。

trace 不进入 context。trace 是调试和审计信息，不应该污染模型决策。完整 chain-of-thought 也不保存，只允许 `reason` 作为简短调试说明。

## 3. 每天 9 点自动复盘任务如何实现？

当前 MVP 没有内置调度器，但设计上可以用外部 scheduler 驱动 Runtime，而不是把定时逻辑塞进 Agent loop。

推荐实现方式：

- 使用 Windows Task Scheduler、cron、GitHub Actions 或后端任务队列在每天 9 点触发。
- scheduler 调用一个脚本，例如 `python scripts/daily_review.py --user alice --session daily_review`。
- 脚本加载对应 session，构造固定 user input，例如“请复盘昨天的待办和重要工具结果，并生成今日计划”。
- Runtime 按普通 turn 执行：构建 context、调用 LLM、必要时调用 todo/search/weather 等工具、保存 final answer 和 trace。

这样定时任务只是 Runtime 的外部入口，不改变核心 Agent loop。好处是职责清晰：scheduler 负责时间，Runtime 负责推理、工具调用、session 和 trace。

## 4. busy session 收到新消息怎么处理？

当前 `JsonSessionStore` 是本地 JSON 文件 MVP，没有实现跨进程锁和并发队列。因此 busy session 的生产级处理需要在 Runtime 外层增加 session-level coordination。

推荐策略：

- 以 `user_id + session_id` 为 key 建立互斥锁或任务队列。
- 如果 session 正在运行，新的 user message 先进入 pending queue。
- 当前 turn 完成后，再按顺序处理 pending messages。
- 如果业务需要实时打断，可以增加 cancel/interruption 状态，但这不是当前 MVP 范围。
- 所有处理结果继续写入同一个 session file 和 trace log，保证可恢复和可审计。

MVP 中已经有 `status` 字段，可以作为后续扩展 busy/running/idle 状态的落点。当前实现适合单进程演示和笔试验证，不声称支持生产级并发写。

## 5. Claude Code/OpenHands 与 OpenAI-compatible function calling 的区别？

这三类能力属于不同层级：

- Claude Code / OpenHands：更接近完整编码 Agent 产品或框架，通常内置规划、文件编辑、命令执行、多步任务管理和运行环境集成。
- OpenAI-compatible function calling：是模型 API 的一种工具调用协议，由 provider 帮你返回结构化 tool call。
- 本项目：自行实现 Agent Runtime 主流程。工具 schema 被注入 context，模型输出本地 JSON action，Parser 解析 action，Runtime 查 ToolRegistry 并执行工具。

本项目没有使用 OpenHands、LangGraph、OpenClaw 等现成 Agent 框架接管主流程，也没有依赖 provider-side function calling。这样做的目的不是比成熟框架功能更多，而是清楚展示 Agent Runtime 的关键部件：session、context、parser、tool registry、tool execution、trace 和 max step loop。

如果后续接 OpenAI-compatible function calling，可以把 provider 返回的 tool calls 转换成现有 `ToolCallAction`，Runtime 主循环仍可复用。但在本 MVP 中，JSON action protocol 更透明，也更能体现核心 Runtime 是自己实现的。
