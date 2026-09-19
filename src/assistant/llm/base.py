"""Contrato del modelo de lenguaje.

Este módulo es el punto de desacoplamiento: el dominio depende solo de estas
abstracciones, nunca de una implementación concreta (Ollama, OpenAI, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Rol de un mensaje dentro de una conversación."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """Un turno de la conversación. Inmutable a propósito."""

    role: Role
    content: str


class LLMError(Exception):
    """Fallo al obtener una respuesta del modelo de lenguaje."""


class LLMProvider(ABC):
    """Interfaz que todo proveedor de LLM debe implementar."""

    @abstractmethod
    def generate(self, messages: list[Message]) -> str:
        """Devuelve la respuesta del modelo a la secuencia de mensajes dada.

        Debe lanzar `LLMError` si no puede completar la petición.
        """
        raise NotImplementedError

    def stream(self, messages: list[Message]) -> Iterator[str]:
        """Genera la respuesta en fragmentos (para mostrarla progresivamente).

        Implementación por defecto: entrega la respuesta completa de `generate()`
        en un único fragmento. Los proveedores que soporten streaming real deben
        sobreescribir este método. Debe lanzar `LLMError` si falla.
        """
        yield self.generate(messages)

    def check_health(self) -> None:
        """Verifica que el proveedor está listo para usarse.

        Debe lanzar `LLMError` con un mensaje accionable si algo falta (servidor
        caído, modelo no descargado...). Por defecto no comprueba nada.
        """
        return None
