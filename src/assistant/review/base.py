"""Contrato del repaso espaciado.

Guarda ítems a repasar (una palabra, un concepto) con una materia y una fecha de
próximo repaso. Al repasar un ítem, esa fecha se aleja según intervalos crecientes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewItem:
    """Un ítem del repaso espaciado."""

    id: int
    subject: str
    text: str
    interval_index: int
    next_review: str  # fecha ISO (YYYY-MM-DD)


class ReviewStore(ABC):
    """Guarda ítems de repaso y calcula qué toca repasar hoy."""

    @abstractmethod
    def add(self, subject: str, text: str) -> ReviewItem:
        """Añade un ítem nuevo (primer repaso al primer intervalo)."""
        raise NotImplementedError

    @abstractmethod
    def due(self, subject: str | None = None) -> list[ReviewItem]:
        """Devuelve los ítems cuyo repaso toca hoy o antes."""
        raise NotImplementedError

    @abstractmethod
    def review(self, item_id: int) -> ReviewItem | None:
        """Marca un ítem como repasado y avanza su próxima fecha. None si no existe."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, item_id: int) -> bool:
        """Elimina un ítem. False si no existe."""
        raise NotImplementedError
