"""Contrato del horario.

Una entrada de horario puede ser de dos tipos:

- **weekly** (recurrente): se repite un día de la semana (gimnasio los miércoles).
  Usa `day` (lunes..domingo). La hora de fin (`end`) es opcional.
- **dated** (puntual): ocurre en una fecha concreta (una reunión el 29/07). Usa
  `date` (ISO YYYY-MM-DD) y normalmente hora de inicio y fin.

Distinguirlas permite responder con precisión a "qué tengo hoy" o "esta semana":
una recurrente cuenta cada semana en su día; una puntual solo en su fecha.

El almacén es compartido: cualquier perfil puede consultarlo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date as date_type

WEEKLY = "weekly"
DATED = "dated"


@dataclass(frozen=True)
class ScheduleEntry:
    id: int
    title: str
    kind: str  # "weekly" | "dated"
    day: str | None  # día de la semana (weekly)
    date: str | None  # fecha ISO (dated)
    start: str  # HH:MM
    end: str | None  # HH:MM o None


class ScheduleStore(ABC):
    @abstractmethod
    def add_weekly(
        self, title: str, day: str, start: str, end: str | None = None
    ) -> ScheduleEntry:
        """Añade un evento recurrente en un día de la semana."""
        raise NotImplementedError

    @abstractmethod
    def add_dated(
        self, title: str, on: str, start: str, end: str | None = None
    ) -> ScheduleEntry:
        """Añade una cita en una fecha concreta (`on` = ISO YYYY-MM-DD)."""
        raise NotImplementedError

    @abstractmethod
    def on_date(self, target: date_type) -> list[ScheduleEntry]:
        """Eventos que ocurren en una fecha: las citas de ese día y las recurrentes
        cuyo día de la semana coincide. Ordenados por hora de inicio."""
        raise NotImplementedError

    @abstractmethod
    def all(self) -> list[ScheduleEntry]:
        """Todas las entradas (para listarlas y editarlas)."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, entry_id: int) -> bool:
        """Elimina una entrada. False si no existe."""
        raise NotImplementedError
