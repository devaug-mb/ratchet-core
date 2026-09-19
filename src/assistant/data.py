"""Vista de solo lectura de los datos del asistente, lista para exponer por API.

Agrupa los almacenes y devuelve estructuras simples (dicts/listas) serializables a
JSON. No contiene lógica de dominio: solo traduce del modelo interno al formato que
consumen los clientes externos (web, móvil, cliente de voz).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from assistant.audit.base import AuditLog
from assistant.items.base import ItemStore
from assistant.memory.base import MemoryStore
from assistant.review.base import ReviewStore
from assistant.schedule.agenda import week_dates, weekday_name
from assistant.schedule.base import ScheduleEntry, ScheduleStore


def _entry_json(entry: ScheduleEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "title": entry.title,
        "kind": entry.kind,
        "day": entry.day,
        "date": entry.date,
        "start": entry.start,
        "end": entry.end,
    }


class DataView:
    def __init__(
        self,
        memory: MemoryStore,
        items: ItemStore,
        schedule: ScheduleStore,
        review: ReviewStore,
        notes_dir: Path,
        audit: AuditLog | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._memory = memory
        self._items = items
        self._schedule = schedule
        self._review = review
        self._notes_dir = notes_dir
        self._audit = audit
        self._today = today

    def memory(self) -> dict[str, str]:
        return self._memory.all()

    def items(self, list_name: str | None = None) -> list[dict[str, object]]:
        return [
            {"id": item.id, "list": item.list_name, "text": item.text, "done": item.done}
            for item in self._items.items(list_name)
        ]

    def schedule_all(self) -> list[dict[str, object]]:
        return [_entry_json(e) for e in self._schedule.all()]

    def schedule_today(self) -> list[dict[str, object]]:
        return [_entry_json(e) for e in self._schedule.on_date(self._today())]

    def schedule_week(self) -> list[dict[str, object]]:
        """Los eventos de cada día de esta semana (solo días con algo)."""
        days: list[dict[str, object]] = []
        for day in week_dates(self._today()):
            entries = self._schedule.on_date(day)
            if entries:
                days.append(
                    {
                        "date": day.isoformat(),
                        "weekday": weekday_name(day),
                        "events": [_entry_json(e) for e in entries],
                    }
                )
        return days

    def review_due(self, subject: str | None = None) -> list[dict[str, object]]:
        return [
            {
                "id": r.id,
                "subject": r.subject,
                "text": r.text,
                "next_review": r.next_review,
            }
            for r in self._review.due(subject)
        ]

    def notes(self) -> list[str]:
        if not self._notes_dir.is_dir():
            return []
        return sorted(path.name for path in self._notes_dir.glob("*.txt"))

    def note(self, name: str) -> str | None:
        """Contenido de una nota. None si no existe o si la ruta se sale de notes/."""
        base = self._notes_dir.resolve()
        target = (base / name).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            return None
        return target.read_text(encoding="utf-8", errors="replace")

    def activity(self, limit: int = 20) -> list[dict[str, object]]:
        if self._audit is None:
            return []
        return [
            {
                "timestamp": e.timestamp,
                "tool": e.tool,
                "arg": e.arg,
                "result": e.result,
                "ok": e.ok,
                "ms": e.ms,
            }
            for e in self._audit.recent(limit)
        ]
