"""Índice de notas con embeddings, sobre SQLite.

Trocea los `.txt` de la carpeta de notas, guarda sus embeddings y busca por
similitud coseno (en Python puro, sin base de datos vectorial). El indexado es
**incremental**: solo se re-embebe una nota si su contenido cambió.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
from pathlib import Path

from assistant.retrieval.base import Embedder, Fragment, Retriever

logger = logging.getLogger(__name__)


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Divide el texto en fragmentos por párrafos, agrupando hasta `max_chars`."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)

    # Trocea en duro los fragmentos que aun así superen el máximo.
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            for start in range(0, len(chunk), max_chars):
                result.append(chunk[start : start + max_chars])
    return result


def cosine(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores. 0 si alguno es nulo o de distinta talla."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class NoteIndex(Retriever):
    """Recupera fragmentos de las notas por parecido semántico."""

    def __init__(
        self,
        notes_dir: Path,
        embedder: Embedder,
        db_path: Path,
        chunk_size: int = 800,
    ) -> None:
        self._notes_dir = notes_dir
        self._embedder = embedder
        self._chunk_size = chunk_size
        if db_path != Path(":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS files (source TEXT PRIMARY KEY, hash TEXT NOT NULL)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            " source TEXT NOT NULL, idx INTEGER NOT NULL,"
            " text TEXT NOT NULL, embedding TEXT NOT NULL)"
        )
        self._connection.commit()

    def index(self) -> None:
        current = self._read_notes()
        stored = dict(
            self._connection.execute("SELECT source, hash FROM files").fetchall()
        )

        for source in stored:
            if source not in current:
                self._forget_source(source)  # nota borrada del disco

        for source, content in current.items():
            digest = hashlib.md5(content.encode("utf-8")).hexdigest()
            if stored.get(source) == digest:
                continue  # sin cambios: no re-embebe
            self._forget_source(source)
            for idx, chunk in enumerate(chunk_text(content, self._chunk_size)):
                embedding = self._embedder.embed(chunk)
                self._connection.execute(
                    "INSERT INTO chunks (source, idx, text, embedding) VALUES (?, ?, ?, ?)",
                    (source, idx, chunk, json.dumps(embedding)),
                )
            self._connection.execute(
                "INSERT INTO files (source, hash) VALUES (?, ?)", (source, digest)
            )
            self._connection.commit()
            logger.info("indexada nota '%s'", source)

    def search(self, query: str, k: int) -> list[Fragment]:
        self.index()
        query_vector = self._embedder.embed(query)
        rows = self._connection.execute(
            "SELECT source, text, embedding FROM chunks"
        ).fetchall()

        fragments = [
            Fragment(source=source, text=text, score=cosine(query_vector, json.loads(emb)))
            for source, text, emb in rows
        ]
        fragments.sort(key=lambda fragment: fragment.score, reverse=True)
        return [fragment for fragment in fragments[:k] if fragment.score > 0]

    def _read_notes(self) -> dict[str, str]:
        if not self._notes_dir.is_dir():
            return {}
        return {
            path.name: path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(self._notes_dir.glob("*.txt"))
        }

    def _forget_source(self, source: str) -> None:
        self._connection.execute("DELETE FROM chunks WHERE source = ?", (source,))
        self._connection.execute("DELETE FROM files WHERE source = ?", (source,))
        self._connection.commit()
