"""Prueba el horario: eventos recurrentes vs. citas puntuales, y sus herramientas."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from assistant.schedule.sqlite_store import SqliteScheduleStore
from assistant.tools.base import ToolError
from assistant.tools.schedule_tools import (
    AddDatedTool,
    AddWeeklyTool,
    RemoveScheduleTool,
    ViewAgendaTool,
)


def _store() -> SqliteScheduleStore:
    return SqliteScheduleStore(Path(":memory:"))


# --- store ------------------------------------------------------------------

def test_on_date_combina_recurrentes_y_citas() -> None:
    store = _store()
    store.add_weekly("gimnasio", "miércoles", "20:00")
    store.add_dated("reunión", "2026-07-29", "10:00", "14:00")  # miércoles

    ese_dia = store.on_date(date(2026, 7, 29))  # miércoles con cita
    assert [(e.title, e.kind) for e in ese_dia] == [
        ("reunión", "dated"),  # ordenado por hora de inicio
        ("gimnasio", "weekly"),
    ]

    otro_miercoles = store.on_date(date(2026, 7, 22))  # solo el recurrente
    assert [e.title for e in otro_miercoles] == ["gimnasio"]

    jueves = store.on_date(date(2026, 7, 23))
    assert jueves == []


def test_add_dated_guarda_fecha_y_fin() -> None:
    store = _store()
    entry = store.add_dated("cita", "2026-08-01", "09:00", "10:30")
    assert entry.kind == "dated"
    assert entry.date == "2026-08-01"
    assert entry.end == "10:30"


def test_remove() -> None:
    store = _store()
    e = store.add_weekly("gimnasio", "lunes", "20:00")
    assert store.remove(e.id) is True
    assert store.all() == []
    assert store.remove(999) is False


def test_migracion_del_esquema_antiguo_convierte_en_recurrente() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "old.db"
        con = sqlite3.connect(str(path))
        con.execute(
            "CREATE TABLE schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT, day TEXT, time TEXT, created_at TEXT)"
        )
        con.execute(
            "INSERT INTO schedule (title, day, time, created_at) "
            "VALUES ('italiano', 'martes', '18:00', 'x')"
        )
        con.commit()
        con.close()

        store = SqliteScheduleStore(path)
        migradas = store.all()
        assert len(migradas) == 1
        assert migradas[0].title == "italiano"
        assert migradas[0].kind == "weekly"
        assert migradas[0].day == "martes"
        assert migradas[0].start == "18:00"


# --- herramientas -----------------------------------------------------------

def test_add_weekly_tool() -> None:
    store = _store()
    AddWeeklyTool(store).run("gimnasio, miércoles, 20:00")
    entry = store.all()[0]
    assert entry.kind == "weekly" and entry.day == "miércoles" and entry.start == "20:00"


def test_add_dated_tool_con_fin() -> None:
    store = _store()
    AddDatedTool(store).run("reunión, 2026-07-29, 10:00, 14:00")
    entry = store.all()[0]
    assert entry.kind == "dated" and entry.date == "2026-07-29" and entry.end == "14:00"


def test_add_dated_tool_rechaza_fecha_invalida() -> None:
    try:
        AddDatedTool(_store()).run("reunión, el martes, 10:00")
    except ToolError:
        pass
    else:
        raise AssertionError("esperaba ToolError")


def test_ver_agenda_hoy() -> None:
    store = _store()
    store.add_weekly("gimnasio", "miércoles", "20:00")
    tool = ViewAgendaTool(store, today=lambda: date(2026, 7, 22))  # miércoles
    salida = tool.run("hoy")
    assert "gimnasio" in salida and "semanal" in salida


def test_ver_agenda_semana_agrupa_por_dia() -> None:
    store = _store()
    store.add_weekly("gimnasio", "miércoles", "20:00")
    store.add_dated("reunión", "2026-07-30", "10:00")  # jueves de esa semana
    tool = ViewAgendaTool(store, today=lambda: date(2026, 7, 27))  # lunes
    salida = tool.run("semana")
    assert "[miércoles" in salida and "gimnasio" in salida
    assert "[jueves" in salida and "reunión" in salida


def test_remove_tool_avisa_si_no_existe() -> None:
    assert "No existe" in RemoveScheduleTool(_store()).run("7")
