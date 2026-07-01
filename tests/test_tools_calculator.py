from __future__ import annotations

import pytest

from tools.calculator import CalculatorTool


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 * 3", 7),
        ("(10 + 2) / 3", 4),
        ("2 ** 8", 256),
        ("-5 + +3", -2),
    ],
)
def test_calculator_evaluates_allowed_arithmetic(expression: str, expected: int | float) -> None:
    result = CalculatorTool().execute({"expression": expression})

    assert result == {"ok": True, "result": expected}


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo unsafe')",
        "eval('1 + 1')",
        "os.system('echo unsafe')",
        "secret_value + 1",
        "'text'",
    ],
)
def test_calculator_rejects_dangerous_expressions(expression: str) -> None:
    result = CalculatorTool().execute({"expression": expression})

    assert result["ok"] is False
    assert "error" in result


def test_calculator_rejects_division_by_zero() -> None:
    result = CalculatorTool().execute({"expression": "1 / 0"})

    assert result["ok"] is False
    assert "division by zero" in result["error"]
