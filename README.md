# Mini Agent Runtime

从零实现的最小可用Agent Runtime，不依赖LangGraph / OpenHands / OpenClaw等现有Agent框架完成主流程。

语言版本：

- [English README](README.en.md)

## 核心能力

- OpenAI-compatible真实LLM API
- Tool Schema注册机制
- calculator / weather / todo / search工具
- Agent Runtime loop
- `user_id + session_id`级session隔离
- context压缩
- trace执行日志
- FakeLLM测试
- pytest 104 passed

## 演示视频

- pytest全量测试通过：104 passed
- 真实LLM调用calculator工具
- weather + todo多工具连续调用
- session隔离演示
- context压缩演示
- trace日志记录与展示
- GitHub Release：[Releases](https://github.com/CodeRunnner/mini-agent-runtime/releases)

## 快速开始

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

复制`.env.example`为`.env`，填写自己的OpenAI-compatible provider配置。不要提交真实API key。

真实LLM模式：

```powershell
python main.py --user alice --session window_1 --llm real --verbose
```

离线fake模式：

```powershell
python main.py --user alice --session window_1 --llm fake
```

运行测试：

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider
```

## 文档

- [架构设计回答](docs/architecture_answers.md)
- [AI辅助开发记录](docs/ai_prompt_log.md)

## 当前边界

- search和weather是mock工具。
- session和trace使用本地JSON / JSONL文件保存。
- context压缩是规则型基础实现。
- Runtime使用本地JSON action协议，没有把核心流程交给provider-side function calling。
