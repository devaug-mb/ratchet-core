"""Prueba el almacén de memoria SQLite, la tool `recordar` y la persistencia."""

from __future__ import annotations

import tempfile
from pathlib import Path

from assistant.memory.sqlite_store import SqliteMemoryStore
from assistant.tools.base import ToolError
from assistant.tools.remember import RememberTool


def _store_en_memoria() -> SqliteMemoryStore:
    return SqliteMemoryStore(Path(":memory:"))


def test_guarda_y_recupera_hechos() -> None:
    store = _store_en_memoria()
    store.remember("nombre", "Alba")
    store.remember("idioma", "alemán")
    assert store.all() == {"idioma": "alemán", "nombre": "Alba"}


def test_remember_actualiza_un_hecho_existente() -> None:
    store = _store_en_memoria()
    store.remember("nivel", "principiante")
    store.remember("nivel", "intermedio")
    assert store.all() == {"nivel": "intermedio"}


def test_forget_elimina_un_hecho() -> None:
    store = _store_en_memoria()
    store.remember("nombre", "Alba")
    store.forget("nombre")
    assert store.all() == {}


def test_recent_devuelve_los_mas_recientes_acotados() -> None:
    store = _store_en_memoria()
    store.remember("a", "1")
    store.remember("b", "2")
    store.remember("c", "3")

    recientes = store.recent(2)
    assert len(recientes) == 2
    assert "c" in recientes  # el último guardado siempre entra
    assert "a" not in recientes  # el más antiguo se queda fuera


def test_los_hechos_sobreviven_entre_sesiones() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "memoria.db"

        primera_sesion = SqliteMemoryStore(db)
        primera_sesion.remember("nombre", "Alba")

        # Nueva sesión: otra instancia sobre el mismo fichero.
        segunda_sesion = SqliteMemoryStore(db)
        assert segunda_sesion.all() == {"nombre": "Alba"}


def test_tool_recordar_guarda_con_formato_clave_valor() -> None:
    store = _store_en_memoria()
    resultado = RememberTool(store).run("nombre: Alba")
    assert store.all() == {"nombre": "Alba"}
    assert "Alba" in resultado


def test_tool_recordar_rechaza_formato_invalido() -> None:
    store = _store_en_memoria()
    try:
        RememberTool(store).run("sin separador")
    except ToolError:
        pass
    else:
        raise AssertionError("esperaba ToolError")
