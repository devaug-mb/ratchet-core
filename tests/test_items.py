"""Prueba el almacén de ítems y las herramientas del organizador."""

from __future__ import annotations

from pathlib import Path

from assistant.items.sqlite_store import SqliteItemStore
from assistant.tools.base import ToolError
from assistant.tools.organizer import (
    AddItemTool,
    CompleteItemTool,
    RemoveItemTool,
    ViewListTool,
)


def _store() -> SqliteItemStore:
    return SqliteItemStore(Path(":memory:"))


def test_add_asigna_id_y_lista() -> None:
    store = _store()
    item = store.add("compra", "leche")
    assert item.id > 0
    assert item.list_name == "compra"
    assert item.done is False


def test_items_filtra_por_lista_y_pendientes() -> None:
    store = _store()
    store.add("tareas", "estudiar")
    comprar = store.add("compra", "pan")
    store.complete(comprar.id)

    assert [i.text for i in store.items("tareas")] == ["estudiar"]
    assert [i.text for i in store.items(pending_only=True)] == ["estudiar"]


def test_complete_y_remove() -> None:
    store = _store()
    item = store.add("tareas", "algo")

    assert store.complete(item.id) is True
    assert store.items("tareas")[0].done is True
    assert store.remove(item.id) is True
    assert store.items("tareas") == []
    assert store.complete(999) is False  # no existe


def test_lists_devuelve_las_listas_con_items() -> None:
    store = _store()
    store.add("tareas", "a")
    store.add("compra", "b")
    assert store.lists() == ["compra", "tareas"]


def test_add_item_tool_usa_lista_por_defecto() -> None:
    store = _store()
    AddItemTool(store).run("comprar regalo")
    assert store.items("tareas")[0].text == "comprar regalo"


def test_add_item_tool_respeta_la_lista() -> None:
    store = _store()
    AddItemTool(store).run("compra: huevos")
    assert store.items("compra")[0].text == "huevos"


def test_view_list_tool_muestra_numeros() -> None:
    store = _store()
    store.add("tareas", "estudiar alemán")
    salida = ViewListTool(store).run("tareas")
    assert "#1" in salida and "estudiar alemán" in salida


def test_complete_item_tool_rechaza_no_numero() -> None:
    try:
        CompleteItemTool(_store()).run("tres")
    except ToolError:
        pass
    else:
        raise AssertionError("esperaba ToolError")


def test_remove_item_tool_avisa_si_no_existe() -> None:
    assert "No existe" in RemoveItemTool(_store()).run("42")
