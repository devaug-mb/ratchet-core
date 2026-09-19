"""Herramientas del horario: eventos recurrentes y citas puntuales."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from assistant.schedule.agenda import week_dates, weekday_name
from assistant.schedule.base import WEEKLY, ScheduleEntry, ScheduleStore
from assistant.tools.base import Tool, ToolError


def _parse_id(arg: str) -> int:
    try:
        return int(arg.strip().lstrip("#").strip())
    except ValueError as exc:
        raise ToolError("indica el número de la entrada (p. ej. '2').") from exc


def _parts(arg: str, minimum: int, maximum: int, formato: str) -> list[str]:
    parts = [p.strip() for p in arg.split(",")]
    if not (minimum <= len(parts) <= maximum) or not all(parts[:minimum]):
        raise ToolError(f"usa el formato: {formato}.")
    return parts


def _time(entry: ScheduleEntry) -> str:
    return entry.start if not entry.end else f"{entry.start}–{entry.end}"


def format_entry(entry: ScheduleEntry) -> str:
    marca = " (semanal)" if entry.kind == WEEKLY else ""
    return f"#{entry.id} {_time(entry)} {entry.title}{marca}"


def format_day(entries: list[ScheduleEntry]) -> str:
    return "\n".join(format_entry(e) for e in entries)


class AddWeeklyTool(Tool):
    name = "agregar_horario_recurrente"
    description = (
        "Añade un evento que se repite cada semana un día fijo (p. ej. gimnasio). "
        "Formato: título, día, hora [, hora_fin]. Ej: 'gimnasio, miércoles, 20:00'."
    )

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        parts = _parts(arg, 3, 4, "título, día, hora [, hora_fin]")
        title, day, start = parts[0], parts[1], parts[2]
        end = parts[3] if len(parts) == 4 and parts[3] else None
        entry = self._store.add_weekly(title, day, start, end)
        return f"Añadido (semanal): {format_entry(entry)}"


class AddDatedTool(Tool):
    name = "agregar_cita"
    description = (
        "Añade una cita en una fecha concreta (p. ej. una reunión). Formato: "
        "título, fecha (YYYY-MM-DD), hora_inicio [, hora_fin]. "
        "Ej: 'reunión, 2026-07-29, 10:00, 14:00'. Usa la herramienta reloj si "
        "necesitas saber la fecha de hoy."
    )

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        parts = _parts(arg, 3, 4, "título, fecha (YYYY-MM-DD), hora [, hora_fin]")
        title, on, start = parts[0], parts[1], parts[2]
        end = parts[3] if len(parts) == 4 and parts[3] else None
        try:
            date.fromisoformat(on)
        except ValueError as exc:
            raise ToolError(f"la fecha '{on}' no es válida (usa YYYY-MM-DD).") from exc
        entry = self._store.add_dated(title, on, start, end)
        return f"Añadida (cita): {format_entry(entry)} el {on}"


class ViewAgendaTool(Tool):
    name = "ver_agenda"
    description = (
        "Muestra la agenda. Argumento: 'hoy' (por defecto), 'semana', o una fecha "
        "YYYY-MM-DD. Combina las citas de ese día con los eventos recurrentes."
    )

    def __init__(self, store: ScheduleStore, today: Callable[[], date] = date.today) -> None:
        self._store = store
        self._today = today

    def run(self, arg: str) -> str:
        query = arg.strip().lower()
        if query in ("", "hoy"):
            entries = self._store.on_date(self._today())
            return format_day(entries) if entries else "No tienes nada hoy."
        if query in ("semana", "esta semana"):
            return self._week()
        try:
            target = date.fromisoformat(query)
        except ValueError:
            return "Dime 'hoy', 'semana' o una fecha (YYYY-MM-DD)."
        entries = self._store.on_date(target)
        return format_day(entries) if entries else f"No hay nada el {query}."

    def _week(self) -> str:
        lines: list[str] = []
        for day in week_dates(self._today()):
            entries = self._store.on_date(day)
            if entries:
                lines.append(f"[{weekday_name(day)} {day.isoformat()}]")
                lines.extend(format_entry(e) for e in entries)
        return "\n".join(lines) if lines else "No tienes nada esta semana."


class RemoveScheduleTool(Tool):
    name = "borrar_horario"
    description = "Elimina una entrada del horario por su número. Argumento: el número."

    def __init__(self, store: ScheduleStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        entry_id = _parse_id(arg)
        if self._store.remove(entry_id):
            return f"Borrada del horario: #{entry_id}"
        return f"No existe la entrada #{entry_id}."
