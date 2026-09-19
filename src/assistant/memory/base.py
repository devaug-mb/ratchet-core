"""Contrato del almacén de memoria persistente.

Igual que con el LLM, el dominio depende de esta abstracción, no de SQLite. Así el
backend de almacenamiento se puede cambiar sin tocar el resto del código.

El modelo de datos es deliberadamente mínimo: hechos clave-valor (texto->texto).
Nada de RAG ni embeddings todavía.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MemoryStore(ABC):
    """Almacena y recupera hechos que sobreviven entre sesiones."""

    @abstractmethod
    def remember(self, key: str, value: str) -> None:
        """Guarda (o actualiza) un hecho."""
        raise NotImplementedError

    @abstractmethod
    def all(self) -> dict[str, str]:
        """Devuelve todos los hechos guardados."""
        raise NotImplementedError

    @abstractmethod
    def forget(self, key: str) -> None:
        """Elimina un hecho. No falla si no existe."""
        raise NotImplementedError

    def recent(self, limit: int) -> dict[str, str]:
        """Devuelve como mucho `limit` hechos, priorizando los más relevantes.

        Se usa para acotar cuánta memoria se inyecta en el prompt. Implementación
        por defecto: los últimos según `all()`. Las implementaciones con marca de
        tiempo deberían devolver los más recientes.
        """
        items = list(self.all().items())
        return dict(items[-limit:]) if limit >= 0 else dict(items)
