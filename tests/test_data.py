"""Prueba la vista de datos que expone la API (estructuras serializables)."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from assistant.audit.jsonl_log import JsonlAuditLog
from assistant.data import DataView
from assistant.items.sqlite_store import SqliteItemStore
from assistant.memory.sqlite_store import SqliteMemoryStore
from assistant.review.sqlite_store import SqliteReviewStore
from assistant.schedule.sqlite_store import SqliteScheduleStore


def _view(notes_dir: Path, audit: JsonlAuditLog | None = None) -> DataView:
    memory = SqliteMemoryStore(Path(":memory:"))
    memory.remember("nombre", "Gus")

    items = SqliteItemStore(Path(":memory:"))
    items.add("compra", "pan")

    schedule = SqliteScheduleStore(Path(":memory:"))
    schedule.add_weekly("alemán", "lunes", "18:00")  # 2026-07-20 es lunes

    review = SqliteReviewStore(
        Path(":memory:"), intervals=(1,), today=lambda: date(2026, 7, 20)
    )
    review.add("alemán", "der Tisch")

    return DataView(
        memory, items, schedule, review, notes_dir, audit,
        today=lambda: date(2026, 7, 20),
    )


def test_memory_items_schedule() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        view = _view(Path(tmp))
        assert view.memory() == {"nombre": "Gus"}
        assert view.items()[0]["text"] == "pan"
        assert view.items("tareas") == []
        # 2026-07-20 es lunes -> el recurrente de los lunes aparece hoy.
        assert view.schedule_today()[0]["title"] == "alemán"
        assert view.schedule_all()[0]["kind"] == "weekly"


def test_schedule_week_agrupa_por_dia() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        view = _view(Path(tmp))  # semana del 2026-07-20 (lunes)
        semana = view.schedule_week()
        # Solo el lunes tiene algo (alemán semanal).
        assert len(semana) == 1
        assert semana[0]["weekday"] == "lunes"
        assert semana[0]["events"][0]["title"] == "alemán"


def test_review_due_usa_la_fecha() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        view = _view(Path(tmp))
        # Añadido "hoy" (2026-07-20) con intervalo 1 día -> aún no toca.
        assert view.review_due() == []


def test_notes_lista_y_lee() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp)
        (notes / "a.txt").write_text("contenido a", encoding="utf-8")
        (notes / "b.txt").write_text("contenido b", encoding="utf-8")
        view = _view(notes)

        assert view.notes() == ["a.txt", "b.txt"]
        assert view.note("a.txt") == "contenido a"
        assert view.note("no_existe.txt") is None


def test_note_bloquea_rutas_fuera_de_la_carpeta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / "notes"
        notes.mkdir()
        (Path(tmp) / "secreto.txt").write_text("secreto", encoding="utf-8")
        view = _view(notes)

        assert view.note("../secreto.txt") is None


def test_activity_devuelve_eventos() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        audit = JsonlAuditLog(Path(tmp) / "activity.log")
        audit.tool_used("calculadora", "1+1", "2", ok=True, ms=1.0)
        view = _view(Path(tmp), audit)

        eventos = view.activity(10)
        assert eventos[0]["tool"] == "calculadora"
        assert eventos[0]["ok"] is True


def test_sin_audit_la_actividad_esta_vacia() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        assert _view(Path(tmp)).activity(10) == []
