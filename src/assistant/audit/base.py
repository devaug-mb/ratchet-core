"""Contrato del registro de actividad.

Un rastro persistente y ordenado de las herramientas usadas, separado del log
técnico de consola. Sirve para responder "¿qué ha hecho el asistente y en qué
orden?" de un vistazo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEvent:
    """Un uso de herramienta registrado."""

    timestamp: str
    tool: str
    arg: str
    result: str
    ok: bool
    ms: float


class AuditLog(ABC):
    """Registra usos de herramientas y permite releer los más recientes."""

    @abstractmethod
    def tool_used(self, tool: str, arg: str, result: str, ok: bool, ms: float) -> None:
        """Añade un evento al registro."""
        raise NotImplementedError

    @abstractmethod
    def recent(self, limit: int) -> list[AuditEvent]:
        """Devuelve los últimos `limit` eventos, en orden cronológico."""
        raise NotImplementedError
