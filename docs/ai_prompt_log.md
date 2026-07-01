# AI辅助开发记录

这个项目里我使用了AI辅助开发，但我没有把它当成“直接生成完整作业”的工具。我的用法更接近结对开发：我让AI帮我拆需求、提出实现方案、补测试和排查错误，但模块边界、MVP范围、安全策略和最终验收标准由我自己决定。

这个项目最核心的限制是：不能用LangGraph、OpenHands、OpenClaw这类现成Agent框架接管主流程。所以我在使用AI时一直围绕一个边界：AI可以帮我写代码和补测试，但不能把核心Runtime变成调用现成框架的壳。

我重点确认了几类问题：

1. 哪些模块必须自己实现，比如Runtime loop、Parser、ToolRegistry、SessionStore、ContextBuilder、TraceLogger；
2. 哪些地方不能为了省事牺牲安全，比如calculator不能直接eval，API key不能写进代码；
3. 哪些能力属于MVP范围，比如本地JSON session、基础context compression、FakeLLM测试；
4. 哪些能力暂时不做生产级包装，比如并发队列、向量数据库、长期全局memory；
5. 真实LLM接入后出现的格式不稳定问题，要通过Parser兼容、fallback和trace来处理，而不是假装模型永远听话。

## 关键取舍

### 1. 不使用现成Agent框架接管主流程

AI一开始可以很容易给出LangChain / LangGraph这类方案，但这个题目的重点是实现Runtime主流程，所以我没有采用这类方案。

最后保留的是自己实现的loop：加载session、构建context、调用LLM、Parser解析action、执行工具、保存状态、写trace、返回final。

这也是项目里`agent/runtime.py`最核心的原因。它把LLMClient、Parser、ToolRegistry、SessionStore、ContextBuilder和TraceLogger串起来，而不是把主流程交给现成框架。

### 2. calculator不用eval

calculator是最容易偷懒的工具。如果直接`eval`，功能上能跑，但安全性很差。

我最后确认用AST白名单，只允许基础数学表达式，不允许任意Python代码执行。这个取舍比“少写几行代码”更重要，因为calculator是面试里最容易被问安全边界的地方。

### 3. 测试使用FakeLLM，而不是依赖真实LLM

真实LLM会受网络、超时、输出格式影响，不适合做稳定测试。

所以我让pytest使用FakeLLM和mock client覆盖Runtime行为，真实LLM只放在demo中演示接入能力。这样测试结果是确定性的，也不会因为外部API波动导致本地测试失败。

当前测试覆盖包括ToolRegistry、Parser、calculator安全计算、Runtime loop、多工具调用、session隔离、context压缩、trace日志、CLI参数、verbose输出、fallback_final和真实模型偶发格式兼容。

### 4. 真实LLM输出不稳定，所以补了兼容层

接入真实LLM后，我遇到过模型直接输出`88`，也遇到过模型把todo工具调用写成`{"type":"todo",...}`。这些问题说明真实模型不会永远按协议输出。

所以我补了两类处理：

- `fallback_final`：工具已经成功执行后，短纯文本可以作为final；
- Parser兼容：把`type=todo`或`action=list`这类输出转换成标准tool_call。

这些不是重写Runtime，而是让Runtime在真实模型环境下更稳。与此同时，我也收紧了fallback条件，避免把JSON工具调用意图误当成final answer。

### 5. trace是为了定位问题，不是为了装饰

我保留trace，是因为Agent行为很容易变成黑盒。

trace记录user_message、llm_output、parse_action、tool_call、tool_result、final_answer、fallback_final和error。这样一旦出错，可以判断是模型输出问题、Parser问题还是工具执行问题。

CLI的`--verbose`只展示compact事件，完整`llm_output`仍然保存在trace里。这样录屏时能看清工具链路，但终端不会被大段模型输出刷乱。

## 最终确认

AI在这个项目里主要帮助我提高实现和排错效率，但几个关键判断是我自己做的：

- 不使用现成Agent框架接管主流程；
- Runtime loop自己实现；
- 工具注册、Parser、Session、Context、Trace拆成独立模块；
- calculator不用危险`eval`；
- 测试不依赖真实LLM；
- API key不提交；
- 真实LLM的不稳定输出通过fallback、Parser兼容和trace处理；
- 最终以pytest 104 passed和录屏demo作为验收。
