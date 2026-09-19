"""Protocolo de invocación de herramientas (Opción A: marcador de texto).

El modelo pide herramientas emitiendo una o más líneas con el formato:

    [[tool:NOMBRE]] ARGUMENTO

Este módulo define cómo se DETECTAN esas peticiones (incluso varias en una misma
respuesta) y cómo se le EXPLICA al modelo. Es dominio puro: no conoce herramientas
concretas ni el proveedor de LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Un marcador completo: nombre + (argumento dentro o después de `]]`).
# El argumento "de fuera" no cruza `[` para no tragarse un marcador siguiente.
_PATTERN = re.compile(
    r"\[\[\s*tool:\s*([a-zA-Z_]+)([^\]\n]*)\]\]([^\n\[]*)",
    re.IGNORECASE,
)

# Inicio de un marcador, para decidir en streaming qué ocultar.
_MARKER_START_RE = re.compile(r"\[\[\s*tool", re.IGNORECASE)
_MARKER_PREFIX = "[[tool"


@dataclass(frozen=True)
class ToolCall:
    """Una petición de herramienta extraída de la respuesta del modelo."""

    name: str
    arg: str


def _to_call(match: re.Match[str]) -> ToolCall:
    inside = match.group(2).strip().lstrip(":").strip()
    after = match.group(3).strip()
    arg = (after or inside).strip("\"'")
    return ToolCall(name=match.group(1).lower(), arg=arg)


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Devuelve todas las llamadas a herramienta del texto, en orden."""
    return [_to_call(match) for match in _PATTERN.finditer(text)]


def parse_tool_call(text: str) -> ToolCall | None:
    """Devuelve la primera llamada a herramienta del texto, o None si no hay."""
    match = _PATTERN.search(text)
    return _to_call(match) if match is not None else None


def marker_start(text: str) -> int:
    """Índice del primer marcador en el texto, o -1 si no hay ninguno."""
    match = _MARKER_START_RE.search(text)
    return match.start() if match is not None else -1


def trailing_partial_len(text: str) -> int:
    """Longitud del sufijo que podría ser el comienzo de un marcador (`[`, `[[`...).

    Sirve para retener, en streaming, un final ambiguo hasta ver el siguiente trozo.
    """
    for length in range(min(len(_MARKER_PREFIX), len(text)), 0, -1):
        if text.endswith(_MARKER_PREFIX[:length]):
            return length
    return 0


def instructions(tool_descriptions: str) -> str:
    """Texto que se añade al prompt de sistema para enseñar a usar las tools."""
    return (
        "Tienes estas herramientas disponibles:\n"
        f"{tool_descriptions}\n\n"
        "IMPORTANTE: para USAR una herramienta debes emitir su marcador. Describir "
        "la acción con palabras NO la ejecuta. SOLO el marcador la ejecuta.\n\n"
        "Cuando necesites herramientas, tu respuesta debe contener ÚNICAMENTE los "
        "marcadores, UNO POR LÍNEA, sin ninguna otra palabra antes ni después:\n"
        "[[tool:NOMBRE]] ARGUMENTO\n\n"
        "Puedes pedir VARIAS herramientas a la vez (una por línea). Recibirás todos "
        "los resultados y ENTONCES, en el siguiente turno, responderás al usuario en "
        "lenguaje natural.\n\n"
        "Reglas:\n"
        "- El ARGUMENTO va después de `]]`, en la misma línea (o vacío si no hace "
        "falta).\n"
        "- No mezcles marcadores con explicaciones en la misma respuesta.\n\n"
        "Ejemplos correctos:\n"
        "[[tool:calculadora]] 3 * (4 + 1)\n"
        "[[tool:ver_horario]]\n"
        "[[tool:buscar_notas]] modelos de lenguaje\n\n"
        "Si no necesitas ninguna herramienta, responde con normalidad."
    )
