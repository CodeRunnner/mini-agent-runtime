# AI 辅助开发记录

这个项目里我确实使用了 AI 辅助开发，主要用来拆需求、补测试、排查 bug 和整理文档。但是 Agent Runtime 的模块边界、实现取舍、安全策略和最后的验收标准，是我自己确认的。

我没有把主流程交给 LangGraph、OpenHands、OpenClaw 这类现成 Agent 框架来做。这个项目的核心目的就是把一个最小可用 Agent Runtime 的关键部件自己串起来，包括 LLM 调用、Parser、ToolRegistry、工具执行、Session、Context 和 Trace。

## 1. 项目骨架

一开始我用 AI 辅助搭了 Python 包结构、CLI 入口、README 和初始测试。  
但我明确限制了范围：这个项目不是要做一个大而全的 Agent 平台，而是先做一个能跑、能测、能解释的最小 Runtime。

所以项目里保留的核心模块是：

- `agent/runtime.py`
- `agent/parser.py`
- `agent/context.py`
- `agent/session.py`
- `agent/trace.py`
- `agent/llm_client.py`
- `agent/tool_registry.py`
- `tools/`
- `scripts/`
- `tests/`

## 2. ToolRegistry

ToolRegistry 是我比较重视的一个点，因为题目要求工具注册机制，而不是在 Runtime 里硬编码几个 if else。

这里 AI 帮我生成了轻量注册表的初版，包括 `register`、`get` 和 schema export。  
我自己确认了工具接口统一成：

```text
name
description
parameters
execute(arguments)

这样 Runtime 不需要关心每个工具内部怎么实现，只需要根据模型输出的 tool_name 找到对应工具并执行。

3. 内置工具

项目里实现了几个工具：

calculator
weather
todo
search

AI 辅助生成了这些工具的初版，我重点检查的是 calculator。因为 calculator 如果直接用 eval，虽然写起来快，但是安全上太差。所以这里我确认使用 AST 白名单解析，只允许基本数学表达式，不允许任意代码执行。

工具输出也统一成结构化 dict，例如：

{"ok": true, "result": 396}

或者：

{"ok": false, "error": "..."}

这样 Runtime 和 trace 都比较好处理。

4. Parser

Parser 这一块主要负责把 LLM 的原始输出转成 Runtime 能执行的 action。
我这里没有让 Parser 去执行工具，也没有让它访问 SessionStore。它只做一件事：解析模型输出。

正常情况下模型应该输出两类 action：

{"type": "tool_call", "tool_name": "calculator", "arguments": {"expression": "23 * 17 + 5"}}

或者：

{"type": "final", "answer": "396"}

后面真实 LLM demo 的时候，我发现模型并不总是严格听话，比如它会输出：

{"type": "todo", "action": "add", "text": "..."}

或者：

{"action": "list"}

所以我又补了兼容逻辑，把这类真实模型偶发输出转换成标准 tool_call。这个属于兼容层，不改变 Runtime 主流程。

5. SessionStore

SessionStore 用来解决同一个用户多个窗口的问题。
我这里的隔离粒度是：

user_id + session_id

也就是说，同一个用户的 window_1 和 window_2 是两个独立 session。

AI 辅助实现了本地 JSON 持久化，我自己确认了两点：

session 文件路径要做安全化处理，避免路径穿越；
todo、summary、messages、tool_results 都要跟 session 绑定，不能混到别的窗口里。

这个设计也是录屏里重点演示的内容：window_1 里有“明早带伞”的待办，window_2 里有“写周报”的待办，两边互不污染。

6. TraceLogger

TraceLogger 是为了让 Agent 行为不是黑盒。

AI 辅助实现了 JSONL trace 日志，我确认 trace 至少要覆盖这些事件：

user_message
llm_output
parse_action
tool_call
tool_result
final_answer
error
fallback_final

这样后面如果工具调用出错，可以看出来到底是模型输出错了、Parser 解析错了，还是工具执行错了。

我觉得这个点比“打印日志”本身更重要。trace 的目的不是装饰，而是复盘 Agent 的行为。

7. ContextBuilder

ContextBuilder 是用来控制每一轮到底把什么内容发给 LLM。

这里我确认了几个原则：

system prompt 要放在最前面，约束模型只能输出本项目定义的 JSON action；
tool schemas 要进入 context，让模型知道能调用什么工具；
summary 用来保存压缩后的旧上下文；
todos 这类结构化状态要单独放，不只依赖自然语言历史；
recent messages 只保留最近几条；
recent tool results 只保留最近重要工具结果；
完整 trace 不进入 context；
不保存也不展示完整 chain-of-thought，只保留简短 reason 字段做调试说明。

这个取舍是为了避免 context 越聊越长，同时又不丢关键状态。

8. AgentRuntime

AgentRuntime 是整个项目的核心。

AI 辅助写了初版循环，但我确认主流程必须由项目自己实现，而不是交给现成 Agent 框架。现在 Runtime 的基本流程是：

加载 session
→ 构建 context
→ 调用 LLM
→ Parser 解析 action
→ 如果是 tool_call，就查 ToolRegistry 并执行工具
→ 保存工具结果
→ 继续下一步 loop
→ 如果是 final，就保存回答并返回
→ 全程写 trace

这里还加了 max_steps，防止模型一直调用工具导致死循环。

todo 工具因为需要读写当前 session，所以在 Runtime 里做了一个 MVP adapter，让 todo 可以访问当前 session 的 todos。这个不是最完美的生产级设计，但对这个最小 Runtime 来说是清楚、可测、可演示的。

9. LLMClient 和 CLI

LLMClient 支持 OpenAI-compatible Chat Completions API。
配置只从环境变量或 .env 读取，不写死在代码里。

我也加了 .env.example，里面只放占位符，不放真实 key。真实 .env 和运行产生的 data/ 都被 .gitignore 忽略。

CLI 支持：

--llm real
--llm fake
--verbose

--verbose 是后面为了录屏补的。因为一开始 CLI 只输出最终答案，比如只输出 396，看不出来中间是否真的调了工具。所以我加了 compact 展示：

[agent] tool_call: calculator ...
[tool] calculator result: ...
[agent] final: ...

这样录屏时能直接看到 Agent 工具调用链路。

10. 真实 LLM demo 中遇到的问题

真实 LLM 接进来以后，最大的问题不是工具不能跑，而是模型输出格式不稳定。

例如：

有时候 calculator 工具已经返回了 88，模型下一步直接输出：

88

但 Parser 原来只认 JSON，所以会报错。

后面我补了 fallback_final：
如果前面已经有成功工具结果，而模型只返回一个很短的纯文本，就把它包装成 final answer，同时在 trace 里标记为 fallback_final。

还有一次 weather 工具调用成功后，模型输出了：

{"type":"todo","action":"add","text":"明早9点根据天气决定是否带伞"}

这其实是 todo 工具调用意图，但格式不是标准 tool_call。所以我又增强了 Parser，兼容这种真实 LLM 偶发格式。

这些修复不是重写 Runtime，而是在真实 API 接入以后补充鲁棒性。

11. 测试

测试主要用 FakeLLM 和 mock client。
我没有让普通 pytest 依赖真实外部 LLM API，因为真实 API 会受网络、超时、模型输出波动影响，不适合做稳定单元测试。

当前测试覆盖包括：

ToolRegistry
calculator 安全计算
Parser
Runtime loop
多工具调用
session 隔离
context 压缩
trace 日志
CLI 参数
verbose 输出
fallback_final
真实模型偶发格式兼容

当前全量测试结果：

104 passed
我的确认

这个项目里 AI 辅助了实现、测试和排错，但我主要确认了下面这些事情：

主流程没有交给现成 Agent 框架；
Runtime loop 是项目自己实现的；
ToolRegistry、Parser、Session、Context、Trace 的职责边界是清楚的；
calculator 没有使用危险的 eval；
测试不依赖真实 LLM API；
真实 API key 不提交；
.env 和 data/ 已经加入 .gitignore；
最终录屏演示的是项目真实能跑的链路，而不是只写文档说明。

---

# `
