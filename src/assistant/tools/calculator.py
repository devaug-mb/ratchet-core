"""Calculadora aritmética segura (sin `eval`).

Evalúa una expresión con un intérprete propio sobre el AST de Python, aceptando
solo números y operadores aritméticos. Así ninguna entrada del modelo puede
ejecutar código arbitrario.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable

from assistant.tools.base import Tool, ToolError

_OPERATORS: dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ToolError("solo se permiten números y operadores aritméticos.")


class Calculator(Tool):
    name = "calculadora"
    description = "Evalúa una expresión aritmética. Argumento de ejemplo: 2 + 2 * 10"

    def run(self, arg: str) -> str:
        try:
            tree = ast.parse(arg, mode="eval")
            result = _evaluate(tree.body)
        except ToolError:
            raise
        except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
            raise ToolError(f"no pude calcular '{arg}': {exc}") from exc
        return str(result)
