"""Herramienta para guardar un hecho en la memoria persistente."""

from __future__ import annotations

from assistant.memory.base import MemoryStore
from assistant.tools.base import Tool, ToolError


class RememberTool(Tool):
    name = "recordar"
    description = (
        "Guarda un dato para recordarlo en futuras sesiones. "
        "Formato: clave: valor (p. ej. 'nombre: Alba'). Puedes agrupar con "
        "categorías usando un punto en la clave (p. ej. 'aleman.nivel: intermedio')."
    )

    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory

    def run(self, arg: str) -> str:
        for separator in (":", "="):
            if separator in arg:
                key, value = arg.split(separator, 1)
                key, value = key.strip(), value.strip()
                if key and value:
                    self._memory.remember(key, value)
                    return f"Guardado: {key} = {value}"
                break
        raise ToolError("usa el formato 'clave: valor'.")
