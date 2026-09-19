"""Prueba el repaso espaciado con un 'hoy' inyectado."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from assistant.review.sqlite_store import SqliteReviewStore
from assistant.tools.review_tools import AddReviewTool, DueReviewsTool, MarkReviewedTool


def _store(today: date) -> SqliteReviewStore:
    return SqliteReviewStore(
        Path(":memory:"), intervals=(1, 3, 7, 15), today=lambda: today
    )


def test_add_programa_el_primer_repaso() -> None:
    store = _store(date(2026, 7, 20))
    item = store.add("alemán", "der Tisch = la mesa")
    assert item.next_review == "2026-07-21"  # hoy + 1 día


def test_due_solo_lo_que_toca() -> None:
    hoy = date(2026, 7, 20)
    store = _store(hoy)
    store.add("alemán", "palabra")  # próximo repaso mañana
    assert store.due() == []  # aún no toca

    manana = _store_reuse(store, date(2026, 7, 21))
    assert [i.text for i in manana.due()] == ["palabra"]


def _store_reuse(store: SqliteReviewStore, new_today: date) -> SqliteReviewStore:
    """Reutiliza la misma conexión pero avanzando el 'hoy'."""
    store._today = lambda: new_today  # type: ignore[attr-defined]
    return store


def test_review_avanza_el_intervalo() -> None:
    store = _store(date(2026, 7, 20))
    item = store.add("alemán", "palabra")  # index 0, +1 día
    revisado = store.review(item.id)
    assert revisado is not None
    assert revisado.interval_index == 1
    assert revisado.next_review == "2026-07-23"  # hoy + 3 días


def test_review_no_pasa_del_ultimo_intervalo() -> None:
    store = _store(date(2026, 7, 20))
    item = store.add("x", "y")
    for _ in range(10):
        store.review(item.id)
    revisado = store.review(item.id)
    assert revisado is not None
    assert revisado.interval_index == 3  # último de (1,3,7,15)


def test_tools_de_repaso() -> None:
    store = _store(date(2026, 7, 20))
    AddReviewTool(store).run("alemán: der Tisch")
    # Mañana toca repasar.
    _store_reuse(store, date(2026, 7, 21))
    assert "der Tisch" in DueReviewsTool(store).run("")
    salida = MarkReviewedTool(store).run("1")
    assert "Próximo repaso" in salida
