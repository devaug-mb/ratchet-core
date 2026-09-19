"""Implementación de `ReviewStore` sobre SQLite.

Repaso espaciado sencillo: intervalos fijos crecientes (1, 3, 7, 15 días). Nada de
algoritmos complejos tipo SM-2. El "hoy" se inyecta (`today`) para poder testear.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from assistant.review.base import ReviewItem, ReviewStore

_DEFAULT_INTERVALS = (1, 3, 7, 15)


class SqliteReviewStore(ReviewStore):
    def __init__(
        self,
        path: Path,
        intervals: tuple[int, ...] = _DEFAULT_INTERVALS,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._intervals = intervals
        self._today = today
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS review ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " subject TEXT NOT NULL,"
            " text TEXT NOT NULL,"
            " interval_index INTEGER NOT NULL,"
            " next_review TEXT NOT NULL)"
        )
        self._connection.commit()

    def _next_date(self, interval_index: int) -> str:
        days = self._intervals[interval_index]
        return (self._today() + timedelta(days=days)).isoformat()

    def add(self, subject: str, text: str) -> ReviewItem:
        next_review = self._next_date(0)
        cursor = self._connection.execute(
            "INSERT INTO review (subject, text, interval_index, next_review)"
            " VALUES (?, ?, 0, ?)",
            (subject, text, next_review),
        )
        self._connection.commit()
        return ReviewItem(cursor.lastrowid, subject, text, 0, next_review)

    def due(self, subject: str | None = None) -> list[ReviewItem]:
        today = self._today().isoformat()
        query = "SELECT id, subject, text, interval_index, next_review FROM review WHERE next_review <= ?"
        params: list[object] = [today]
        if subject is not None:
            query += " AND subject = ?"
            params.append(subject)
        query += " ORDER BY next_review, id"
        rows = self._connection.execute(query, params).fetchall()
        return [ReviewItem(*row) for row in rows]

    def review(self, item_id: int) -> ReviewItem | None:
        row = self._connection.execute(
            "SELECT id, subject, text, interval_index FROM review WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            return None
        new_index = min(row[3] + 1, len(self._intervals) - 1)
        next_review = self._next_date(new_index)
        self._connection.execute(
            "UPDATE review SET interval_index = ?, next_review = ? WHERE id = ?",
            (new_index, next_review, item_id),
        )
        self._connection.commit()
        return ReviewItem(row[0], row[1], row[2], new_index, next_review)

    def remove(self, item_id: int) -> bool:
        cursor = self._connection.execute("DELETE FROM review WHERE id = ?", (item_id,))
        self._connection.commit()
        return cursor.rowcount > 0
