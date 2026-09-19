"""Implementación de `ScheduleStore` sobre SQLite.

Guarda eventos recurrentes (weekly) y citas puntuales (dated) en la misma tabla,
distinguidos por `kind`. Migra automáticamente el esquema antiguo (solo día + hora)
convirtiendo esas entradas en recurrentes, para no perder datos.
"""

from __future__ import annotations

import sqlite3
from datetime import date as date_type
from datetime import datetime
from pathlib import Path

from assistant.schedule.agenda import day_order, normalize_weekday, weekday_name
from assistant.schedule.base import DATED, WEEKLY, ScheduleEntry, ScheduleStore

_COLUMNS = "id, title, kind, weekday, on_date, start_time, end_time"


def _row(row: tuple) -> ScheduleEntry:
    return ScheduleEntry(
        id=row[0], title=row[1], kind=row[2], day=row[3], date=row[4],
        start=row[5], end=row[6],
    )


class SqliteScheduleStore(ScheduleStore):
    def __init__(self, path: Path) -> None:
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        if self._needs_migration():
            self._migrate_from_v1()
        self._create_table()

    # --- esquema ----------------------------------------------------------------

    def _columns(self) -> set[str]:
        rows = self._connection.execute("PRAGMA table_info(schedule)").fetchall()
        return {row[1] for row in rows}

    def _needs_migration(self) -> bool:
        columns = self._columns()
        return "time" in columns and "kind" not in columns

    def _create_table(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schedule ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " weekday TEXT,"
            " on_date TEXT,"
            " start_time TEXT NOT NULL,"
            " end_time TEXT,"
            " created_at TEXT NOT NULL)"
        )
        self._connection.commit()

    def _migrate_from_v1(self) -> None:
        self._connection.execute("ALTER TABLE schedule RENAME TO schedule_v1")
        self._create_table()
        # Las entradas antiguas (día + hora) pasan a recurrentes.
        self._connection.execute(
            "INSERT INTO schedule (title, kind, weekday, on_date, start_time, end_time, created_at)"
            " SELECT title, ?, day, NULL, time, NULL, created_at FROM schedule_v1",
            (WEEKLY,),
        )
        self._connection.execute("DROP TABLE schedule_v1")
        self._connection.commit()

    # --- escritura --------------------------------------------------------------

    def add_weekly(
        self, title: str, day: str, start: str, end: str | None = None
    ) -> ScheduleEntry:
        weekday = normalize_weekday(day)
        cursor = self._connection.execute(
            "INSERT INTO schedule (title, kind, weekday, on_date, start_time, end_time, created_at)"
            " VALUES (?, ?, ?, NULL, ?, ?, ?)",
            (title, WEEKLY, weekday, start, end, datetime.now().isoformat()),
        )
        self._connection.commit()
        return ScheduleEntry(cursor.lastrowid, title, WEEKLY, weekday, None, start, end)

    def add_dated(
        self, title: str, on: str, start: str, end: str | None = None
    ) -> ScheduleEntry:
        cursor = self._connection.execute(
            "INSERT INTO schedule (title, kind, weekday, on_date, start_time, end_time, created_at)"
            " VALUES (?, ?, NULL, ?, ?, ?, ?)",
            (title, DATED, on, start, end, datetime.now().isoformat()),
        )
        self._connection.commit()
        return ScheduleEntry(cursor.lastrowid, title, DATED, None, on, start, end)

    # --- lectura ----------------------------------------------------------------

    def on_date(self, target: date_type) -> list[ScheduleEntry]:
        weekday = weekday_name(target)
        iso = target.isoformat()
        rows = self._connection.execute(
            f"SELECT {_COLUMNS} FROM schedule"
            " WHERE (kind = ? AND weekday = ?) OR (kind = ? AND on_date = ?)",
            (WEEKLY, weekday, DATED, iso),
        ).fetchall()
        entries = [_row(row) for row in rows]
        entries.sort(key=lambda entry: entry.start)
        return entries

    def all(self) -> list[ScheduleEntry]:
        rows = self._connection.execute(f"SELECT {_COLUMNS} FROM schedule").fetchall()
        entries = [_row(row) for row in rows]
        weekly = sorted(
            (e for e in entries if e.kind == WEEKLY),
            key=lambda e: (day_order(e.day or ""), e.start),
        )
        dated = sorted(
            (e for e in entries if e.kind == DATED),
            key=lambda e: (e.date or "", e.start),
        )
        return [*weekly, *dated]

    def remove(self, entry_id: int) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM schedule WHERE id = ?", (entry_id,)
        )
        self._connection.commit()
        return cursor.rowcount > 0
