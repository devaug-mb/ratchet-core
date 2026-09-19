"""Contratos de la búsqueda semántica.

Como con el LLM y la memoria, el resto del código depende de estas abstracciones,
no de una implementación concreta (embeddings de Ollama, SQLite...).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmbeddingError(Exception):
    """Fallo al generar un embedding (modelo no disponible, servidor caído...)."""


@dataclass(frozen=True)
class Fragment:
    """Un fragmento de nota recuperado, con su origen y su parecido con la consulta."""

    source: str
    text: str
    score: float


class Embedder(ABC):
    """Convierte texto en un vector numérico (embedding)."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Devuelve el embedding del texto. Lanza `EmbeddingError` si falla."""
        raise NotImplementedError


class Retriever(ABC):
    """Indexa un corpus y recupera los fragmentos más relevantes a una consulta."""

    @abstractmethod
    def index(self) -> None:
        """Asegura que el índice está al día (incremental)."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, k: int) -> list[Fragment]:
        """Devuelve hasta `k` fragmentos ordenados por relevancia."""
        raise NotImplementedError
