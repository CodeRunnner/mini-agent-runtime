"""Safe calculator tool."""

from __future__ import annotations

import ast
import operator
from typing import Any


class CalculatorTool:
    name = "calculator"
    description = "Evaluate a simple arithmetic expression."
    parameters = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Arithmetic expression to evaluate."}
        },
        "required": ["expression"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute a safe arithmetic calculation."""
        expression = arguments.get("expression") if isinstance(arguments, dict) else None
        if not isinstance(expression, str) or not expression.strip():
            return {"ok": False, "error": "expression must be a non-empty string"}
        if "_" in expression:
            return {"ok": False, "error": "expression contains forbidden characters"}

        try:
            tree = ast.parse(expression, mode="eval")
            result = _SafeArithmeticEvaluator().visit(tree)
        except (SyntaxError, ValueError, ZeroDivisionError) as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, "result": result}


class _SafeArithmeticEvaluator(ast.NodeVisitor):
    """Evaluate a small whitelist of arithmetic AST nodes."""

    _binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    _unary_operators = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def visit_Expression(self, node: ast.Expression) -> int | float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> int | float:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("only numeric constants are allowed")
        return value

    def visit_BinOp(self, node: ast.BinOp) -> int | float:
        operator_type = type(node.op)
        if operator_type not in self._binary_operators:
            raise ValueError(f"operator is not allowed: {operator_type.__name__}")

        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent is too large")
        return self._binary_operators[operator_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> int | float:
        operator_type = type(node.op)
        if operator_type not in self._unary_operators:
            raise ValueError(f"operator is not allowed: {operator_type.__name__}")

        operand = self.visit(node.operand)
        return self._unary_operators[operator_type](operand)

    def generic_visit(self, node: ast.AST) -> int | float:
        raise ValueError(f"expression contains forbidden syntax: {type(node).__name__}")
