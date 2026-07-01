# AI 辅助开发记录

这个项目里我使用了 AI 辅助开发，但我没有把它当成“直接生成完整作业”的工具。我的用法更接近结对开发：我让 AI 帮我拆需求、提出实现方案、补测试和排查错误，但模块边界、MVP 范围、安全策略和最终验收标准由我自己决定。

这个项目最核心的限制是：不能用 LangGraph、OpenHands、OpenClaw 这类现成 Agent 框架接管主流程。所以我在使用 AI 时一直围绕一个边界：AI 可以帮我写代码和补测试，但不能把核心 Runtime 变成调用现成框架的壳。

我重点确认了几类问题：

1. 哪些模块必须自己实现，比如 Runtime loop、Parser、ToolRegistry、SessionStore、ContextBuilder、TraceLogger；
2. 哪些地方不能为了省事牺牲安全，比如 calculator 不能直接 eval，API key 不能写进代码；
3. 哪些能力属于 MVP 范围，比如本地 JSON session、基础 context compression、FakeLLM 测试；
4. 哪些能力暂时不做生产级包装，比如并发队列、向量数据库、长期全局 memory；
5. 真实 LLM 接入后出现的格式不稳定问题，要通过 Parser 兼容、fallback 和 trace 来处理，而不是假装模型永远听话。

## 关键取舍

### 1. 不使用现成 Agent 框架接管主流程

AI 一开始可以很容易给出 LangChain / LangGraph 这类方案，但这个题目的重点是实现 Runtime 主流程，所以我没有采用这类方案。

最后保留的是自己实现的 loop：加载 session、构建 context、调用 LLM、Parser 解析 action、执行工具、保存状态、写 trace、返回 final。

这也是项目里 `agent/runtime.py` 最核心的原因。它把 LLMClient、Parser、ToolRegistry、SessionStore、ContextBuilder 和 TraceLogger 串起来，而不是把主流程交给现成框架。

### 2. calculator 不用 eval

calculator 是最容易偷懒的工具。如果直接 `eval`，功能上能跑，但安全性很差。

我最后确认用 AST 白名单，只允许基础数学表达式，不允许任意 Python 代码执行。这个取舍比“少写几行代码”更重要，因为 calculator 是面试里最容易被问安全边界的地方。

### 3. 测试使用 FakeLLM，而不是依赖真实 LLM

真实 LLM 会受网络、超时、输出格式影响，不适合做稳定测试。

所以我让 pytest 使用 FakeLLM 和 mock client 覆盖 Runtime 行为，真实 LLM 只放在 demo 中演示接入能力。这样测试结果是确定性的，也不会因为外部 API 波动导致本地测试失败。

当前测试覆盖包括 ToolRegistry、Parser、calculator 安全计算、Runtime loop、多工具调用、session 隔离、context 压缩、trace 日志、CLI 参数、verbose 输出、fallback_final 和真实模型偶发格式兼容。

### 4. 真实 LLM 输出不稳定，所以补了兼容层

接入真实 LLM 后，我遇到过模型直接输出 `88`，也遇到过模型把 todo 工具调用写成 `{"type":"todo",...}`。这些问题说明真实模型不会永远按协议输出。

所以我补了两类处理：

- `fallback_final`：工具已经成功执行后，短纯文本可以作为 final；
- Parser 兼容：把 `type=todo` 或 `action=list` 这类输出转换成标准 tool_call。

这些不是重写 Runtime，而是让 Runtime 在真实模型环境下更稳。与此同时，我也收紧了 fallback 条件，避免把 JSON 工具调用意图误当成 final answer。

### 5. trace 是为了定位问题，不是为了装饰

我保留 trace，是因为 Agent 行为很容易变成黑盒。

trace 记录 user_message、llm_output、parse_action、tool_call、tool_result、final_answer、fallback_final 和 error。这样一旦出错，可以判断是模型输出问题、Parser 问题还是工具执行问题。

CLI 的 `--verbose` 只展示 compact 事件，完整 `llm_output` 仍然保存在 trace 里。这样录屏时能看清工具链路，但终端不会被大段模型输出刷乱。

## 最终确认

AI 在这个项目里主要帮助我提高实现和排错效率，但几个关键判断是我自己做的：

- 不使用现成 Agent 框架接管主流程；
- Runtime loop 自己实现；
- 工具注册、Parser、Session、Context、Trace 拆成独立模块；
- calculator 不用危险 `eval`；
- 测试不依赖真实 LLM；
- API key 不提交；
- 真实 LLM 的不稳定输出通过 fallback、Parser 兼容和 trace 处理；
- 最终以 pytest 104 passed 和录屏 demo 作为验收。
