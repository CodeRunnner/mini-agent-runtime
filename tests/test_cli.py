from __future__ import annotations

import importlib
from pathlib import Path

from agent.cli import build_runtime, build_tool_registry, main
from agent.llm_client import FakeLLMClient


def test_build_tool_registry_registers_builtin_tools() -> None:
    registry = build_tool_registry()

    assert {schema["name"] for schema in registry.schemas()} == {
        "calculator",
        "search",
        "weather",
        "todo",
    }


def test_fake_mode_builds_runtime_without_llm_env(tmp_path: Path) -> None:
    runtime = build_runtime(fake=True, data_dir=tmp_path)

    assert isinstance(runtime.llm_client, FakeLLMClient)
    assert runtime.run_turn("user_1", "session_1", "hello").startswith("Fake mode is running")


def test_llm_fake_mode_builds_runtime_without_llm_env(tmp_path: Path) -> None:
    runtime = build_runtime(llm="fake", data_dir=tmp_path)

    assert isinstance(runtime.llm_client, FakeLLMClient)


def test_cli_fake_mode_can_start_and_quit(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "quit")

    result = main(["--fake", "--user", "user_1", "--session", "session_1", "--data-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "mini-agent-runtime started" in captured.out
    assert "user=user_1" in captured.out


def test_cli_llm_fake_mode_can_start_and_quit(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "quit")

    result = main(["--llm", "fake", "--user", "user_1", "--session", "session_1", "--data-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "mini-agent-runtime started" in captured.out


def test_cli_loads_dotenv_for_real_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=openai_compatible",
                "LLM_API_KEY=dotenv-key",
                "LLM_MODEL=dotenv-model",
                "LLM_BASE_URL=https://example.test/v1",
                "LLM_TEMPERATURE=0",
            ]
        ),
        encoding="utf-8",
    )
    for name in [
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_BASE_URL",
        "LLM_TEMPERATURE",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt="": "quit")

    result = main(["--llm", "real", "--user", "user_1", "--session", "session_1", "--data-dir", str(tmp_path / "data")])

    captured = capsys.readouterr()
    assert result == 0
    assert "mini-agent-runtime started" in captured.out


def test_root_main_module_exposes_cli_main() -> None:
    entrypoint = importlib.import_module("main")

    assert entrypoint.main is main
