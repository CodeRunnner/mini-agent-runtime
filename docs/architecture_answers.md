# 架构设计回答

这部分是我基于这个项目的实际实现做的架构回答。我没有把答案写成一个很大的生产级系统方案，而是按我这次真正做过的内容来回答：当前 MVP 怎么做，为什么这么取舍，如果继续往后扩展，应该补在哪一层。

## 1. 如果用户连续聊 200 轮，怎么管理 context？

如果用户连续聊 200 轮，我肯定不会把所有历史消息都原样塞回 LLM。这样做看起来简单，但实际问题很多：token 成本会越来越高，响应会变慢，也可能超过上下文窗口。更麻烦的是，太多旧消息会干扰模型判断，模型不一定知道当前最重要的上下文是什么。

所以我这个项目里没有做“全量历史回放”，而是做了一个分层 context。

完整 session 会保存在本地 JSON 里，但每一轮真正发给 LLM 的内容由 `ContextBuilder` 控制。大致分成几类：

- system prompt：约束模型按本项目的 JSON action 协议输出；
- tool schemas：告诉模型有哪些工具可以调用；
- summary：保存较早历史压缩后的稳定信息；
- structured state：比如当前 session 的 todos；
- recent messages：只保留最近几条原始消息；
- recent tool results：只保留最近几个重要工具结果。

我这里比较重视 structured state。比如 todo 这种东西，如果只靠自然语言历史保存，很容易在压缩后丢掉或者被模型理解错。所以 todo 是单独存在 session state 里的，不只是存在聊天记录里。

当消息数量超过阈值后，`BasicContextCompressor` 会把旧消息压进 summary，然后只保留最近消息。录屏里我用 `demo_compress.py` 模拟长对话，再用 `show_session.py` 看结果：summary 有内容，message_count 被压到 8，todos 和 tool_results 还在。

这个方案不是最复杂的，但对 MVP 来说够清楚：旧消息进 summary，最近消息保留原文，关键状态结构化保存，工具结果保留近期重要结果。

如果后面要做得更强，可以加向量召回或者按任务类型做 memory retrieval。但我这次没有直接上向量库，因为当前题目更重要的是先把 Runtime 主链路跑通，而不是一开始就堆复杂组件。

## 2. memory 什么时候召回，放在 context 的什么位置？

我这次做的是 session 级 memory，不是全局长期记忆。也就是说，memory 是跟 `user_id + session_id` 绑定的。这样可以解决同一个用户多个窗口的问题，比如 `alice/window_1` 和 `alice/window_2` 不会互相污染。

每一轮 Runtime 开始时，会先加载当前 session，然后由 `ContextBuilder` 决定哪些内容放进 context。

我放入 context 的顺序大概是：

1. system prompt；
2. tool schemas；
3. session summary；
4. structured state，比如 todos；
5. recent tool results；
6. recent messages；
7. 当前用户输入。

这样排是有原因的。system prompt 和工具 schema 要靠前，因为它们决定模型输出格式和可调用工具。summary 和 structured state 也要靠前，因为它们是当前 session 的稳定状态。recent messages 和 recent tool results 放后面，用来支持短期追问。

比如用户问：

```text
刚才北京天气怎么样？我明早要做什么？
```

这句话本身没有完整信息。如果没有 memory，模型只能瞎猜。但当前 session 里有 weather 工具结果，也有 todo 状态，所以 Runtime 会把这些放进 context，模型就能回答：北京天气多云，22°C，明早需要根据天气决定是否带伞。

我没有把 trace 放进 context。trace 是给开发者看的，不是给模型继续推理用的。如果把 trace 全塞进去，模型反而会被日志干扰。

我也没有保存完整 chain-of-thought。项目里只保留一个简短 `reason` 字段，用来调试模型为什么调用某个工具。完整推理过程不进入 session，也不进入 trace。

## 3. 如果要每天早上 9 点自动复盘，怎么实现？

这个功能我不会直接塞进 Agent Runtime 里面。Runtime 应该负责“收到一次输入后怎么推理、怎么调用工具、怎么保存状态”，而不是负责“每天几点触发”。

所以如果要做每天 9 点自动复盘，我会在 Runtime 外面加一个 scheduler。

流程可以是：

1. Windows Task Scheduler、cron、GitHub Actions 或后端任务队列每天 9 点触发；
2. 调用一个脚本，比如 `scripts/daily_review.py`；
3. 脚本指定 `user_id` 和 `session_id`；
4. 构造一条固定输入，比如“请根据昨天的待办和重要工具结果生成今日复盘”；
5. 然后交给 `AgentRuntime` 正常执行；
6. Runtime 继续负责 context、LLM、工具调用、session 保存和 trace。

这样做的好处是职责比较干净：scheduler 只负责时间，Runtime 只负责 Agent 执行。

如果把定时逻辑也塞进 Runtime，后面会很乱：聊天入口、定时入口、任务队列入口全混在一起，不好测，也不好扩展。

如果后面真的做生产级版本，我还会补几个点：

- 每天任务有唯一 `task_id`，避免重复执行；
- LLM 或工具失败要写 error trace；
- 自动复盘结果写入固定 session，比如 `daily_review`；
- 用户当天打开聊天时，可以继续追问这次复盘内容。

当前 MVP 没有实现 scheduler，但这个扩展点是清楚的。它应该作为 Runtime 外层入口，而不是改 Runtime 主循环。

## 4. session 正在执行工具调用时，又来了新消息怎么办？

这个问题本质上是并发和状态一致性问题。

如果同一个 session 里，前一个请求还在执行工具，后一个消息又进来了，不能让两个 Runtime loop 同时写同一个 session。否则可能出现消息顺序乱了、todo 被重复添加、工具结果覆盖、trace 对不上。

当前项目是本地 JSON 文件的 MVP，主要用于单进程演示和笔试验证。我不会说它已经支持生产级并发写，这个不真实。

如果要扩展，我会在 Runtime 外层加 session-level lock 或 queue。粒度就是 `user_id + session_id`。

也就是说：

- `alice/window_1` 同一时间只能有一个 Runtime loop 在写；
- 如果 `window_1` 正在执行，新消息先进入 pending queue；
- 当前 turn 完成后，再处理下一条；
- 但 `alice/window_1` 和 `alice/window_2` 可以并发，因为它们是两个不同 session。

大致流程是：

```text
收到用户消息
-> 获取 session lock
-> 写入 user message
-> 执行 Runtime loop
-> 保存 tool_result / final_answer / trace
-> 释放 lock
-> 处理 pending message
```

如果工具调用超时，Runtime 要写 error trace，并把 session 状态恢复成 idle，不能让 session 永远卡在 running。

当前项目里已经有 `status` 字段，可以作为后续扩展 busy/running/idle 的落点。这个点我不会过度包装，目前就是 MVP，但扩展方向是明确的。

## 5. Claude Code / OpenHands 和 OpenAI-compatible function calling 有什么区别？

我理解它们不是同一个层级的东西。

OpenAI-compatible function calling 更像一种模型 API 协议。它解决的是：模型怎么用结构化方式告诉外部系统“我要调用哪个工具，参数是什么”。

但 function calling 本身不是完整 Agent Runtime。它不负责：

- session 怎么保存；
- context 怎么压缩；
- 工具结果怎么进入下一轮；
- 多工具 loop 怎么控制；
- trace 怎么记录；
- 工具失败怎么恢复；
- 多 session 怎么隔离。

这些还是 Runtime 层要做的事情。

Claude Code、OpenHands 这类东西更像完整的软件开发 Agent 产品或框架。它们通常不只是 tool call，而是会集成文件读写、代码搜索、shell 执行、项目修改、多步规划、人机确认和运行环境管理。

本项目做的是中间这一层：最小可用 Agent Runtime。

我没有使用 LangGraph、OpenHands、OpenClaw 这类现成框架来接管主流程，也没有依赖 provider-side function calling。我的做法是把 tool schemas 注入 context，让模型输出本项目定义的 JSON action，然后 Parser 把它转成 `ToolCallAction` 或 `FinalAnswerAction`，最后 Runtime 查 `ToolRegistry` 执行工具。

这样做的好处是透明。虽然功能不如成熟框架多，但能清楚看到 Agent Runtime 的关键部件是怎么工作的：

- `LLMClient`
- `Parser`
- `ToolRegistry`
- `AgentRuntime`
- `SessionStore`
- `ContextBuilder`
- `TraceLogger`

如果以后要接 provider-side function calling，也可以把 provider 返回的 tool calls 转换成项目内部的 `ToolCallAction`，Runtime 主循环仍然可以复用。

所以我会这样总结：

- function calling 是工具调用协议；
- Claude Code / OpenHands 是完整软件开发 Agent；
- 这个项目是我自己实现的最小 Agent Runtime，用来展示中间这层的机制。
