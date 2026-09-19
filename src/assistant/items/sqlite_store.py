"""Implementación de `ItemStore` sobre SQLite (librería estándar, sin ORM)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from assistant.items.base import Item, ItemStore


class SqliteItemStore(ItemStore):
    """Guarda los ítems en una tabla `items`."""

    def __init__(self, path: Path) -> None:
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS items ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " list_name TEXT NOT NULL,"
            " text TEXT NOT NULL,"
            " done INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )
        self._connection.commit()

    def add(self, list_name: str, text: str) -> Item:
        cursor = self._connection.execute(
            "INSERT INTO items (list_name, text, done, created_at) VALUES (?, ?, 0, ?)",
            (list_name, text, datetime.now().isoformat()),
        )
        self._connection.commit()
        return Item(id=cursor.lastrowid, list_name=list_name, text=text, done=False)

    def items(self, list_name: str | None = None, pending_only: bool = False) -> list[Item]:
        query = "SELECT id, list_name, text, done FROM items"
        conditions: list[str] = []
        params: list[object] = []
        if list_name is not None:
            conditions.append("list_name = ?")
            params.append(list_name)
        if pending_only:
            conditions.append("done = 0")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id"

        rows = self._connection.execute(query, params).fetchall()
        return [
            Item(id=row[0], list_name=row[1], text=row[2], done=bool(row[3]))
            for row in rows
        ]

    def complete(self, item_id: int) -> bool:
        cursor = self._connection.execute(
            "UPDATE items SET done = 1 WHERE id = ?", (item_id,)
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def remove(self, item_id: int) -> bool:
        cursor = self._connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self._connection.commit()
        return cursor.rowcount > 0

    def lists(self) -> list[str]:
        rows = self._connection.execute(
            "SELECT DISTINCT list_name FROM items ORDER BY list_name"
        ).fetchall()
        return [row[0] for row in rows]
