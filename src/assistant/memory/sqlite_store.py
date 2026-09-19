"""Implementación de `MemoryStore` sobre SQLite (librería estándar, sin ORM).

Mantiene una única conexión durante la vida del proceso. Ligero y suficiente para
un asistente personal de un solo usuario en una Raspberry Pi.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from assistant.memory.base import MemoryStore


class SqliteMemoryStore(MemoryStore):
    """Guarda los hechos en una tabla `facts (key, value, updated_at)`."""

    def __init__(self, path: Path) -> None:
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: la web usa hilos, pero el acceso está
        # serializado con un lock, así que es seguro. El CLI es de un solo hilo.
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS facts ("
            " key TEXT PRIMARY KEY,"
            " value TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._connection.commit()

    def remember(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
            " updated_at = excluded.updated_at",
            (key, value, datetime.now().isoformat()),
        )
        self._connection.commit()

    def all(self) -> dict[str, str]:
        rows = self._connection.execute(
            "SELECT key, value FROM facts ORDER BY key"
        ).fetchall()
        return {key: value for key, value in rows}

    def recent(self, limit: int) -> dict[str, str]:
        rows = self._connection.execute(
            "SELECT key, value FROM facts ORDER BY updated_at DESC, key LIMIT ?",
            (limit,),
        ).fetchall()
        return {key: value for key, value in rows}

    def forget(self, key: str) -> None:
        self._connection.execute("DELETE FROM facts WHERE key = ?", (key,))
        self._connection.commit()
