# 架构设计回答

这部分是我对 Agent Runtime 架构题的回答。回答不是按“生产级大系统”去吹，而是基于这个项目当前 MVP 的实现来说明：现在做到了什么、为什么这样做、后续如果扩展应该往哪里加。

---

## 1. 如果用户连续聊 200 轮，怎么管理 context？

如果用户连续聊 200 轮，肯定不能把所有历史消息原样塞回 LLM。  
这样不仅 token 成本高，响应慢，而且很容易超过上下文窗口。更麻烦的是，太多旧消息还可能干扰模型判断。

所以我这里的设计不是“全量塞历史”，而是分层管理 context。

当前项目里 session 会完整保存到本地 JSON，但每一轮真正发给 LLM 的内容，是由 `ContextBuilder` 控制的，主要包括：

- system prompt：约束模型只能输出项目定义的 JSON action；
- tool schemas：告诉模型当前有哪些工具可以调用；
- session summary：保存旧对话压缩后的稳定信息；
- structured state：比如当前 session 的 todos；
- recent messages：只保留最近几条原始消息，默认 8 条；
- recent tool results：只保留最近几个工具结果，默认 3 个。

当消息数量超过阈值时，`BasicContextCompressor` 会把较旧的消息压缩进 `session_state.summary`，然后只保留最近消息。

这个设计的核心思路是：

```text
旧消息进入 summary
最近消息保留原文
结构化状态单独保存
工具结果只保留关键近期结果

这样即使聊到 200 轮，Runtime 也不会把 200 轮全部丢进 prompt，但用户目标、待办事项、重要工具结果和近期上下文还可以保留下来。

在录屏里我用 scripts/demo_compress.py 模拟长对话，然后用 scripts/show_session.py 展示压缩后的结果。可以看到 summary 有内容，message_count 变成 8，同时 todos 和 tool_results 没丢。

2. memory 什么时候召回，放在 context 的什么位置？

我这里没有做全局长期记忆，也没有上向量数据库。当前 MVP 主要做的是 session 级 memory。

每一轮 Runtime 开始时，会先根据：

user_id + session_id

加载对应的 session。然后 ContextBuilder.build_messages() 决定哪些 memory 要进入这轮 context。

召回的内容主要有几类：

session summary

用来保存被压缩的旧上下文，比如用户之前的目标、未完成事项、重要工具结果。

structured state

比如 todos。这个不能只放在自然语言历史里，因为 todo 是明确状态，应该结构化保存。

recent messages

用来支持“刚才说了什么”“继续上一个问题”这类短期追问。

recent tool results

用来支持工具链后续推理，比如刚查过天气，下一轮用户问“刚才北京天气怎么样”。

放入 context 的顺序大致是：

system prompt
→ tool schemas
→ session summary
→ structured state
→ recent tool results
→ recent messages
→ current user input

这里我特意没有把 trace 放进 context。
trace 是给开发者调试和审计用的，不应该污染模型的判断。

完整 chain-of-thought 也不保存。项目里只允许模型输出一个简短 reason 字段，用于调试，不存完整推理过程。

举个例子，用户问：

刚才北京天气怎么样？我明早要做什么？

Runtime 会把当前 session 里的 weather 工具结果、todo 状态和最近对话放进 context。模型就能回答：北京天气是多云、22°C，明早需要根据天气决定是否带伞。

3. 每天早上 9 点自动复盘任务怎么实现？

当前项目是 MVP，没有内置 scheduler。
如果要做每天早上 9 点自动复盘，我不会把定时逻辑硬塞进 Agent Runtime 里，而是会在 Runtime 外面加一个 scheduler。

原因是：
scheduler 负责“什么时候触发”，Runtime 负责“触发后怎么推理、怎么调工具、怎么写 session 和 trace”。这两个职责最好分开。

一个比较清楚的流程是：

Windows Task Scheduler / cron / GitHub Actions / 后端任务队列
→ 每天 9 点触发脚本
→ 脚本指定 user_id 和 session_id
→ 构造一条固定用户输入
→ 调用 AgentRuntime
→ Runtime 正常构建 context、调用 LLM、必要时调工具
→ 保存复盘结果
→ 写 trace

比如可以有一个脚本：

python scripts/daily_review.py --user alice --session daily_review

它构造的输入可以是：

请根据昨天的待办、重要工具结果和当前 session summary，生成今日早间复盘。

这样做的好处是，自动任务和普通聊天复用同一套 Runtime。
todo、summary、tool_results、trace 都不需要重新设计。

如果做得更完整一点，还要考虑：

每天任务要有唯一 task_id，避免重复执行；
LLM 或工具失败要写 error trace；
自动任务结果要保存到固定 session；
如果用户当天打开聊天窗口，也能追问这次复盘内容。

当前 MVP 还没实现 daily scheduler，但这个扩展点是清楚的。

4. session 正在执行工具调用时，又来了新消息怎么办？

这个问题本质上是并发和状态一致性问题。

如果同一个 session 里，前一个请求还在跑工具，后一个用户消息又进来了，不能让两个 Runtime loop 同时写同一个 session 文件。否则可能出现：

消息顺序错乱；
todo 重复添加；
工具结果覆盖；
trace 对不上；
session 状态被写坏。

我当前这个项目是本地 JSON 文件 MVP，适合单进程演示和笔试验证，没有声称支持生产级并发写。但如果要扩展，我会在 Runtime 外层加 session-level coordination。

核心策略是：

以 user_id + session_id 为 key 加锁或排队

也就是说：

alice/window_1 同一时间只允许一个 Runtime loop 写；
如果 window_1 正在 busy，新的消息进入 pending queue；
当前 turn 完成后，再按顺序处理下一条消息；
不同 session，比如 alice/window_1 和 alice/window_2，可以并发，因为它们状态隔离。

流程大概是：

收到 user message
→ 获取 session lock
→ append message
→ 执行 AgentRuntime loop
→ 写入 tool_results / assistant answer / trace
→ 释放 session lock
→ 处理 pending message

如果工具调用超时，Runtime 要写 error trace，并把 session 状态恢复成 idle，避免 session 永久卡死。

当前项目里已经有 status 字段，可以作为后续扩展 busy/running/idle 的落点。
这个 MVP 现在重点是把 Runtime 主链路做清楚，而不是假装已经解决了生产级并发。

5. Claude Code / OpenHands 和 OpenAI-compatible function calling 有什么区别？

我理解这几个东西不在一个层级。

Claude Code、OpenHands 更像完整的软件开发 Agent 产品或框架。它们通常不只是“调用工具”，还会包含：

读写文件；
搜索代码；
执行 shell 命令；
修改项目；
多步任务规划；
人机确认；
运行环境管理；
更复杂的安全边界。

而 OpenAI-compatible function calling 更像是一种模型 API 的工具调用协议。
它解决的是：模型如何用结构化方式表达“我要调用哪个工具，参数是什么”。

比如模型可能返回：

{
  "tool_name": "calculator",
  "arguments": {
    "expression": "23 * 17 + 5"
  }
}

但 function calling 本身不等于完整 Agent Runtime。它通常不会自动帮你解决：

session 怎么保存；
context 怎么压缩；
工具结果怎么进入下一轮；
多工具 loop 怎么控制；
trace 怎么记录；
失败怎么恢复；
多 session 怎么隔离。

这些还是需要 Runtime 层自己处理。

本项目做的就是这个中间层：
不依赖 LangGraph、OpenHands、OpenClaw 这类现成框架，而是自己实现一个最小 Agent Runtime。

当前项目没有使用 provider-side function calling，而是把 tool schemas 注入 context，让模型输出本地 JSON action，再由 Parser 转成 ToolCallAction 或 FinalAnswerAction，最后 Runtime 查 ToolRegistry 执行工具。

这样做的好处是透明：
我能清楚展示 Agent Runtime 的几个关键部件是怎么协作的：

LLMClient
Parser
ToolRegistry
AgentRuntime
SessionStore
ContextBuilder
TraceLogger

如果后续要接 OpenAI-compatible function calling，也可以把 provider 返回的 tool calls 转换成项目内部的 ToolCallAction，Runtime 主循环仍然可以复用。

所以简单说：

function calling 是模型和工具之间的调用协议；
Claude Code / OpenHands 是完整的软件开发 Agent 系统；
本项目是自己实现一个最小 Agent Runtime，用来展示中间这层怎么工作。
