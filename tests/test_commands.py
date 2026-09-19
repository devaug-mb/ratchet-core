"""Prueba el framework de comandos y los comandos concretos."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from assistant.commands import Command, CommandRegistry, CommandResult, build_commands
from assistant.items.sqlite_store import SqliteItemStore
from assistant.memory.sqlite_store import SqliteMemoryStore
from assistant.schedule.sqlite_store import SqliteScheduleStore


def _items() -> SqliteItemStore:
    return SqliteItemStore(Path(":memory:"))


def test_dispatch_devuelve_none_si_no_es_comando() -> None:
    registry = CommandRegistry([])
    assert registry.dispatch("hola, esto es un mensaje normal") is None


def test_help_lista_los_comandos() -> None:
    registry = CommandRegistry(
        [Command("saluda", "Saluda.", lambda _: CommandResult("hola"))]
    )
    ayuda = registry.dispatch("/help")
    assert ayuda is not None
    assert "/saluda" in ayuda.output
    assert "/help" in ayuda.output


def test_comando_desconocido_sugiere_help() -> None:
    resultado = CommandRegistry([]).dispatch("/inventado")
    assert resultado is not None
    assert "/help" in resultado.output


def test_memoria_lista_los_hechos() -> None:
    memory = SqliteMemoryStore(Path(":memory:"))
    memory.remember("nombre", "Gus")
    registry = build_commands("system", Path("prompts"), memory, _items())

    resultado = registry.dispatch("/memoria")
    assert resultado is not None
    assert "nombre" in resultado.output and "Gus" in resultado.output


def test_memoria_agrupa_por_categoria() -> None:
    memory = SqliteMemoryStore(Path(":memory:"))
    memory.remember("aleman.nivel", "intermedio")
    memory.remember("aleman.objetivo", "B2")
    memory.remember("nombre", "Gus")
    registry = build_commands("system", Path("prompts"), memory, _items())

    salida = registry.dispatch("/memoria").output
    assert "[aleman]" in salida
    assert "[(general)]" in salida


def test_memoria_muestra_un_dato_concreto() -> None:
    memory = SqliteMemoryStore(Path(":memory:"))
    memory.remember("nombre", "Gus")
    registry = build_commands("system", Path("prompts"), memory, _items())

    resultado = registry.dispatch("/memoria nombre")
    assert resultado is not None
    assert resultado.output == "nombre: Gus"


def test_olvidar_elimina_un_hecho() -> None:
    memory = SqliteMemoryStore(Path(":memory:"))
    memory.remember("nombre", "Gus")
    registry = build_commands("system", Path("prompts"), memory, _items())

    resultado = registry.dispatch("/olvidar nombre")
    assert resultado is not None
    assert "Olvidado" in resultado.output
    assert memory.all() == {}


def test_salir_marca_exit() -> None:
    registry = build_commands(
        "system", Path("prompts"), SqliteMemoryStore(Path(":memory:")), _items()
    )
    resultado = registry.dispatch("/salir")
    assert resultado is not None
    assert resultado.exit is True


def test_perfil_muestra_los_disponibles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "system.txt").write_text("x", encoding="utf-8")
        (directory / "aleman.txt").write_text("x", encoding="utf-8")
        registry = build_commands(
            "system", directory, SqliteMemoryStore(Path(":memory:")), _items()
        )

        resultado = registry.dispatch("/perfil")
        assert resultado is not None
        assert "aleman" in resultado.output and "system" in resultado.output


def test_tareas_lista_los_items() -> None:
    items = SqliteItemStore(Path(":memory:"))
    items.add("tareas", "estudiar")
    registry = build_commands(
        "system", Path("prompts"), SqliteMemoryStore(Path(":memory:")), items
    )

    salida = registry.dispatch("/tareas").output
    assert "estudiar" in salida


def test_compra_vacia_avisa() -> None:
    registry = build_commands(
        "system", Path("prompts"), SqliteMemoryStore(Path(":memory:")), _items()
    )
    assert "No hay nada" in registry.dispatch("/compra").output


def test_horario_lista_la_semana() -> None:
    schedule = SqliteScheduleStore(Path(":memory:"))
    schedule.add_weekly("alemán", "lunes", "18:00")
    registry = build_commands(
        "asistente",
        Path("prompts"),
        SqliteMemoryStore(Path(":memory:")),
        _items(),
        schedule,
        today=lambda: date(2026, 7, 20),  # semana con un lunes
    )

    salida = registry.dispatch("/horario").output
    assert "alemán" in salida and "lunes" in salida


def test_sin_schedule_no_hay_comando_horario() -> None:
    registry = build_commands(
        "system", Path("prompts"), SqliteMemoryStore(Path(":memory:")), _items()
    )
    # Sin store de horario, /horario no existe como comando conocido.
    assert "desconocido" in registry.dispatch("/horario").output
