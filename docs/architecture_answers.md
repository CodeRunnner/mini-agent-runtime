# 架构设计回答

这部分是我基于这个项目的实际实现做的架构回答。我没有把答案写成一个很大的生产级系统方案，而是按我这次真正做过的内容来回答：当前MVP怎么做，为什么这么取舍，如果继续往后扩展，应该补在哪一层。

## 1. 如果用户连续聊200轮，怎么管理context？

如果用户连续聊200轮，我肯定不会把所有历史消息都原样塞回LLM。这样做看起来简单，但实际问题很多：token成本会越来越高，响应会变慢，也可能超过上下文窗口。更麻烦的是，太多旧消息会干扰模型判断，模型不一定知道当前最重要的上下文是什么。

所以我这个项目里没有做“全量历史回放”，而是做了一个分层context。

完整session会保存在本地JSON里，但每一轮真正发给LLM的内容由`ContextBuilder`控制。大致分成几类：

- system prompt：约束模型按本项目的JSON action协议输出；
- tool schemas：告诉模型有哪些工具可以调用；
- summary：保存较早历史压缩后的稳定信息；
- structured state：比如当前session的todos；
- recent messages：只保留最近几条原始消息；
- recent tool results：只保留最近几个重要工具结果。

我这里比较重视structured state。比如todo这种东西，如果只靠自然语言历史保存，很容易在压缩后丢掉或者被模型理解错。所以todo是单独存在session state里的，不只是存在聊天记录里。

当消息数量超过阈值后，`BasicContextCompressor`会把旧消息压进summary，然后只保留最近消息。录屏里我用`demo_compress.py`模拟长对话，再用`show_session.py`看结果：summary有内容，message_count被压到8，todos和tool_results还在。

这个方案不是最复杂的，但对MVP来说够清楚：旧消息进summary，最近消息保留原文，关键状态结构化保存，工具结果保留近期重要结果。

如果后面要做得更强，可以加向量召回或者按任务类型做memory retrieval。但我这次没有直接上向量库，因为当前题目更重要的是先把Runtime主链路跑通，而不是一开始就堆复杂组件。

## 2. memory什么时候召回，放在context的什么位置？

我这次做的是session级memory，不是全局长期记忆。也就是说，memory是跟`user_id + session_id`绑定的。这样可以解决同一个用户多个窗口的问题，比如`alice/window_1`和`alice/window_2`不会互相污染。

每一轮Runtime开始时，会先加载当前session，然后由`ContextBuilder`决定哪些内容放进context。

我放入context的顺序大概是：

1. system prompt；
2. tool schemas；
3. session summary；
4. structured state，比如todos；
5. recent tool results；
6. recent messages；
7. 当前用户输入。

这样排是有原因的。system prompt和工具schema要靠前，因为它们决定模型输出格式和可调用工具。summary和structured state也要靠前，因为它们是当前session的稳定状态。recent messages和recent tool results放后面，用来支持短期追问。

比如用户问：

```text
刚才北京天气怎么样？我明早要做什么？
```

这句话本身没有完整信息。如果没有memory，模型只能瞎猜。但当前session里有weather工具结果，也有todo状态，所以Runtime会把这些放进context，模型就能回答：北京天气多云，22°C，明早需要根据天气决定是否带伞。

我没有把trace放进context。trace是给开发者看的，不是给模型继续推理用的。如果把trace全塞进去，模型反而会被日志干扰。

我也没有保存完整chain-of-thought。项目里只保留一个简短`reason`字段，用来调试模型为什么调用某个工具。完整推理过程不进入session，也不进入trace。

## 3. 如果要每天早上9点自动复盘，怎么实现？

这个功能我不会直接塞进Agent Runtime里面。Runtime应该负责“收到一次输入后怎么推理、怎么调用工具、怎么保存状态”，而不是负责“每天几点触发”。

所以如果要做每天9点自动复盘，我会在Runtime外面加一个scheduler。

流程可以是：

1. Windows Task Scheduler、cron、GitHub Actions或后端任务队列每天9点触发；
2. 调用一个脚本，比如`scripts/daily_review.py`；
3. 脚本指定`user_id`和`session_id`；
4. 构造一条固定输入，比如“请根据昨天的待办和重要工具结果生成今日复盘”；
5. 然后交给`AgentRuntime`正常执行；
6. Runtime继续负责context、LLM、工具调用、session保存和trace。

这样做的好处是职责比较干净：scheduler只负责时间，Runtime只负责Agent执行。

如果把定时逻辑也塞进Runtime，后面会很乱：聊天入口、定时入口、任务队列入口全混在一起，不好测，也不好扩展。

如果后面真的做生产级版本，我还会补几个点：

- 每天任务有唯一`task_id`，避免重复执行；
- LLM或工具失败要写error trace；
- 自动复盘结果写入固定session，比如`daily_review`；
- 用户当天打开聊天时，可以继续追问这次复盘内容。

当前MVP没有实现scheduler，但这个扩展点是清楚的。它应该作为Runtime外层入口，而不是改Runtime主循环。

## 4. session正在执行工具调用时，又来了新消息怎么办？

这个问题本质上是并发和状态一致性问题。

如果同一个session里，前一个请求还在执行工具，后一个消息又进来了，不能让两个Runtime loop同时写同一个session。否则可能出现消息顺序乱了、todo被重复添加、工具结果覆盖、trace对不上。

当前项目是本地JSON文件的MVP，主要用于单进程演示和笔试验证。我不会说它已经支持生产级并发写，这个不真实。

如果要扩展，我会在Runtime外层加session-level lock或queue。粒度就是`user_id + session_id`。

也就是说：

- `alice/window_1`同一时间只能有一个Runtime loop在写；
- 如果`window_1`正在执行，新消息先进入pending queue；
- 当前turn完成后，再处理下一条；
- 但`alice/window_1`和`alice/window_2`可以并发，因为它们是两个不同session。

大致流程是：

```text
收到用户消息
-> 获取session lock
-> 写入user message
-> 执行Runtime loop
-> 保存tool_result / final_answer / trace
-> 释放lock
-> 处理pending message
```

如果工具调用超时，Runtime要写error trace，并把session状态恢复成idle，不能让session永远卡在running。

当前项目里已经有`status`字段，可以作为后续扩展busy/running/idle的落点。这个点我不会过度包装，目前就是MVP，但扩展方向是明确的。

## 5. Claude Code / OpenHands和OpenAI-compatible function calling有什么区别？

我理解它们不是同一个层级的东西。

OpenAI-compatible function calling更像一种模型API协议。它解决的是：模型怎么用结构化方式告诉外部系统“我要调用哪个工具，参数是什么”。

但function calling本身不是完整Agent Runtime。它不负责：

- session怎么保存；
- context怎么压缩；
- 工具结果怎么进入下一轮；
- 多工具loop怎么控制；
- trace怎么记录；
- 工具失败怎么恢复；
- 多session怎么隔离。

这些还是Runtime层要做的事情。

Claude Code、OpenHands这类东西更像完整的软件开发Agent产品或框架。它们通常不只是tool call，而是会集成文件读写、代码搜索、shell执行、项目修改、多步规划、人机确认和运行环境管理。

本项目做的是中间这一层：最小可用Agent Runtime。

我没有使用LangGraph、OpenHands、OpenClaw这类现成框架来接管主流程，也没有依赖provider-side function calling。我的做法是把tool schemas注入context，让模型输出本项目定义的JSON action，然后Parser把它转成`ToolCallAction`或`FinalAnswerAction`，最后Runtime查`ToolRegistry`执行工具。

这样做的好处是透明。虽然功能不如成熟框架多，但能清楚看到Agent Runtime的关键部件是怎么工作的：

- `LLMClient`
- `Parser`
- `ToolRegistry`
- `AgentRuntime`
- `SessionStore`
- `ContextBuilder`
- `TraceLogger`

如果以后要接provider-side function calling，也可以把provider返回的tool calls转换成项目内部的`ToolCallAction`，Runtime主循环仍然可以复用。

所以我会这样总结：

- function calling是工具调用协议；
- Claude Code / OpenHands是完整软件开发Agent；
- 这个项目是我自己实现的最小Agent Runtime，用来展示中间这层的机制。
