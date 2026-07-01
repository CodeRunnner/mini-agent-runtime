# 录屏演示脚本

本文档用于录屏或现场演示 MVP 提交版本。

## 1. 准备环境

进入项目目录并安装依赖：

```powershell
cd D:\myproject\mini-agent-runtime
D:\Anaconda\python.exe -m pip install -r requirements.txt
```

清理旧 demo 数据：

```powershell
Remove-Item -Recurse -Force .\data -ErrorAction SilentlyContinue
```

运行全量测试：

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

录屏时说明：

- 当前测试应显示 `104 passed`。
- 普通 pytest 不会调用真实外部 LLM API。
- Runtime 行为通过 FakeLLM 和 mock client 做确定性测试。

## 2. fake 模式演示

运行：

```powershell
python main.py --user demo_user --session fake_window --llm fake
```

输入：

```text
hello
quit
```

录屏时说明：

- 这是离线 smoke path。
- CLI 会构造真实的本地 `AgentRuntime`，注册内置工具，并注入 FakeLLM。
- fake 模式不会调用外部 API。

## 3. 真实 LLM 模式演示

复制 `.env.example` 为 `.env`，填写真实 provider 配置：

```powershell
Copy-Item .env.example .env
notepad .env
```

不要在录屏里展示真实 `.env` 内容。

运行：

```powershell
python main.py --user demo_user --session real_window --llm real --verbose
```

建议输入：

```text
请通过 calculator 工具计算 23 * 17 + 5，并在得到工具结果后直接返回最终答案。
请查一下北京天气，并帮我记一个待办：明早9点根据天气决定是否带伞。
我的待办有哪些？
quit
```

录屏时说明：

- 真实 client 调用 OpenAI-compatible chat completions endpoint。
- CLI 启动时会自动加载项目根目录下的 `.env`。
- 模型输出 JSON action，本地 Parser 解析 action。
- Runtime 通过 `ToolRegistry` 执行工具，保存 session，并写 trace。
- `--verbose` 只打印 compact 的 tool_call、tool_result、final_answer 和 error，不打印完整 `llm_output`。

## 4. session 隔离演示

打开两个终端。

窗口 1：

```powershell
python main.py --user demo_user --session window_1 --llm real --verbose
```

窗口 2：

```powershell
python main.py --user demo_user --session window_2 --llm real --verbose
```

分别添加不同待办，然后回到窗口 1 查询待办。

录屏时说明：

- session state 以 `user_id + session_id` 隔离。
- `window_1` 和 `window_2` 会写入不同的 session JSON 文件。
- todo 在 Runtime 内部是 session-aware 的，不会互相污染。

## 5. trace 日志展示

运行：

```powershell
python scripts/show_trace.py --user demo_user --session real_window --limit 20
```

预期能看到这些事件类型：

- `user_message`
- `llm_output`
- `parse_action`
- `tool_call`
- `tool_result`
- `final_answer`
- `fallback_final`
- `error`

录屏时说明：

- trace 是 JSONL，一行一个事件。
- trace 用于调试和审计，不直接塞进 LLM context。
- 完整 `llm_output` 可以通过 trace 查看，CLI verbose 模式只展示简化事件。

## 6. session 文件展示

运行：

```powershell
python scripts/show_session.py --user demo_user --session real_window
```

录屏时说明：

- session 文件包含 user message、assistant message、tool message、tool results、todos、summary 和时间戳。
- 这是 MVP 的本地 JSON 持久化，不是生产级数据库。
- 当前没有跨进程写锁，生产环境需要 session-level queue 或 lock。

## 7. context 压缩演示

运行：

```powershell
python scripts/demo_compress.py --user demo_user --session compress_window
python scripts/show_session.py --user demo_user --session compress_window
```

录屏时说明：

- context 压缩是规则型基础实现。
- 旧消息会被压缩进 summary。
- 最近消息、todos 和 tool results 会保留，用于支持追问。
