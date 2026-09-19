"""Herramientas del repaso espaciado."""

from __future__ import annotations

from assistant.review.base import ReviewItem, ReviewStore
from assistant.tools.base import Tool, ToolError

_DEFAULT_SUBJECT = "general"


def _parse_id(arg: str) -> int:
    try:
        return int(arg.strip().lstrip("#").strip())
    except ValueError as exc:
        raise ToolError("indica el número del ítem (p. ej. '3').") from exc


def format_reviews(items: list[ReviewItem]) -> str:
    return "\n".join(f"#{item.id} [{item.subject}] {item.text}" for item in items)


class AddReviewTool(Tool):
    name = "agregar_repaso"
    description = (
        "Añade algo para repasar más adelante (repaso espaciado). Formato: "
        "materia: texto (p. ej. 'alemán: der Tisch = la mesa')."
    )

    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        if ":" in arg:
            subject, text = arg.split(":", 1)
            subject, text = subject.strip().lower(), text.strip()
        else:
            subject, text = _DEFAULT_SUBJECT, arg.strip()
        if not text:
            raise ToolError("indica qué quieres repasar.")
        item = self._store.add(subject, text)
        return f"Añadido para repasar [{subject}]: {text} (#{item.id})"


class DueReviewsTool(Tool):
    name = "repasos_pendientes"
    description = "Muestra lo que toca repasar hoy. No necesita argumento."

    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        subject = arg.strip().lower() or None
        items = self._store.due(subject)
        if not items:
            return "Nada que repasar hoy."
        return format_reviews(items)


class MarkReviewedTool(Tool):
    name = "marcar_repasado"
    description = (
        "Marca un ítem de repaso como hecho por su número; se reprograma para más "
        "adelante. Argumento: el número."
    )

    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        item_id = _parse_id(arg)
        item = self._store.review(item_id)
        if item is None:
            return f"No existe el ítem de repaso #{item_id}."
        return f"Repasado #{item_id}. Próximo repaso: {item.next_review}."
