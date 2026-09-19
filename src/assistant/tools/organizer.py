"""Herramientas del asistente organizador: gestionar listas de ítems.

Cuatro herramientas genéricas cubren tareas, compra y cualquier otra lista, sin
inflar el prompt con una herramienta por lista.
"""

from __future__ import annotations

from assistant.items.base import Item, ItemStore
from assistant.tools.base import Tool, ToolError

_DEFAULT_LIST = "tareas"


def _parse_id(arg: str) -> int:
    try:
        return int(arg.strip().lstrip("#").strip())
    except ValueError as exc:
        raise ToolError("indica el número del elemento (p. ej. '3').") from exc


def format_items(items: list[Item]) -> str:
    """Lista los ítems agrupados por lista, con su número y estado."""
    groups: dict[str, list[Item]] = {}
    for item in items:
        groups.setdefault(item.list_name, []).append(item)

    lines: list[str] = []
    for list_name in sorted(groups):
        lines.append(f"[{list_name}]")
        for item in groups[list_name]:
            mark = "x" if item.done else " "
            lines.append(f"#{item.id} [{mark}] {item.text}")
    return "\n".join(lines)


class AddItemTool(Tool):
    name = "agregar_item"
    description = (
        "Añade un elemento a una lista. Formato: lista: texto (p. ej. "
        "'compra: leche'). Si no indicas lista, va a 'tareas'."
    )

    def __init__(self, store: ItemStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        if ":" in arg:
            list_name, text = arg.split(":", 1)
            list_name, text = list_name.strip().lower(), text.strip()
        else:
            list_name, text = _DEFAULT_LIST, arg.strip()
        if not text:
            raise ToolError("indica qué añadir.")
        item = self._store.add(list_name, text)
        return f"Añadido a {list_name}: {text} (#{item.id})"


class ViewListTool(Tool):
    name = "ver_lista"
    description = (
        "Muestra los elementos de una lista (o de todas si no indicas nombre). "
        "Argumento: nombre de la lista, opcional."
    )

    def __init__(self, store: ItemStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        list_name = arg.strip().lower() or None
        items = self._store.items(list_name)
        if not items:
            return (
                f"No hay elementos en '{list_name}'."
                if list_name
                else "No hay ninguna lista con elementos."
            )
        return format_items(items)


class CompleteItemTool(Tool):
    name = "completar_item"
    description = "Marca un elemento como hecho por su número. Argumento: el número."

    def __init__(self, store: ItemStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        item_id = _parse_id(arg)
        if self._store.complete(item_id):
            return f"Hecho: #{item_id}"
        return f"No existe el elemento #{item_id}."


class RemoveItemTool(Tool):
    name = "borrar_item"
    description = "Elimina un elemento por su número. Argumento: el número."

    def __init__(self, store: ItemStore) -> None:
        self._store = store

    def run(self, arg: str) -> str:
        item_id = _parse_id(arg)
        if self._store.remove(item_id):
            return f"Borrado: #{item_id}"
        return f"No existe el elemento #{item_id}."
