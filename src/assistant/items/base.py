"""Contrato del almacén de ítems estructurados.

Modelo mínimo y general: listas con nombre que contienen ítems (texto + estado).
Sirve igual para una lista de tareas, la de la compra o cualquier otra. Como el
resto del proyecto, el dominio depende de esta interfaz, no de SQLite.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    """Un elemento de una lista."""

    id: int
    list_name: str
    text: str
    done: bool


class ItemStore(ABC):
    """Guarda y recupera ítems agrupados en listas con nombre."""

    @abstractmethod
    def add(self, list_name: str, text: str) -> Item:
        """Añade un ítem a una lista y lo devuelve (con su id asignado)."""
        raise NotImplementedError

    @abstractmethod
    def items(self, list_name: str | None = None, pending_only: bool = False) -> list[Item]:
        """Devuelve los ítems, opcionalmente de una lista y/o solo los pendientes."""
        raise NotImplementedError

    @abstractmethod
    def complete(self, item_id: int) -> bool:
        """Marca un ítem como hecho. Devuelve False si no existe."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, item_id: int) -> bool:
        """Elimina un ítem. Devuelve False si no existe."""
        raise NotImplementedError

    @abstractmethod
    def lists(self) -> list[str]:
        """Nombres de las listas que tienen algún ítem."""
        raise NotImplementedError
