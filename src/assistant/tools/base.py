"""Contrato de una herramienta.

Una herramienta recibe un argumento de texto y devuelve un resultado de texto. Es
deliberadamente simple: el modelo la invoca con una línea de texto (ver
`core/tool_protocol.py`) y recibe una respuesta de texto.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ToolError(Exception):
    """Error esperado al ejecutar una herramienta (p. ej. argumento inválido)."""


class Tool(ABC):
    """Herramienta invocable por el asistente.

    `name` es un identificador simple (letras y guiones bajos) usado en el marcador
    `[[tool:name]]`. `description` se muestra al modelo para que sepa cuándo y cómo
    usar la herramienta.
    """

    name: str
    description: str

    @abstractmethod
    def run(self, arg: str) -> str:
        """Ejecuta la herramienta con el argumento y devuelve el resultado.

        Debe lanzar `ToolError` si el argumento no es válido.
        """
        raise NotImplementedError
