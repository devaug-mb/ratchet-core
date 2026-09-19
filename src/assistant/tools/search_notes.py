"""Herramienta de búsqueda semántica en las notas del usuario."""

from __future__ import annotations

from assistant.retrieval.base import EmbeddingError, Retriever
from assistant.tools.base import Tool, ToolError


class SearchNotesTool(Tool):
    name = "buscar_notas"
    description = (
        "Busca en las notas del usuario por significado (no por nombre de archivo) "
        "y devuelve los fragmentos más relevantes. Argumento: la consulta o tema."
    )

    def __init__(self, retriever: Retriever, k: int = 3) -> None:
        self._retriever = retriever
        self._k = k

    def run(self, arg: str) -> str:
        query = arg.strip()
        if not query:
            raise ToolError("indica qué quieres buscar en las notas.")
        try:
            fragments = self._retriever.search(query, self._k)
        except EmbeddingError as exc:
            raise ToolError(str(exc)) from exc

        if not fragments:
            return "No encontré nada relevante en las notas."
        return "\n\n".join(f"[{fragment.source}]\n{fragment.text}" for fragment in fragments)
