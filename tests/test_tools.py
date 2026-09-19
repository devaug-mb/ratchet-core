"""Prueba cada herramienta de forma aislada y el registro."""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from assistant.tools.base import ToolError
from assistant.tools.calculator import Calculator
from assistant.tools.clock import Clock
from assistant.tools.file_reader import FileReader
from assistant.tools.registry import ToolBox


class _ListHandler(logging.Handler):
    """Captura los mensajes de log emitidos, sin depender de pytest."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _capture(logger_name: str) -> _ListHandler:
    handler = _ListHandler()
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return handler


def test_calculadora_evalua_expresiones() -> None:
    assert Calculator().run("2 + 2 * 10") == "22"


def test_calculadora_rechaza_lo_que_no_es_aritmetica() -> None:
    try:
        Calculator().run("__import__('os')")
    except ToolError:
        pass
    else:
        raise AssertionError("esperaba ToolError")


def test_reloj_usa_la_hora_inyectada() -> None:
    fija = datetime(2026, 7, 18, 9, 30, 0)
    assert Clock(now=lambda: fija).run("") == "2026-07-18 09:30:00"


def test_leer_archivo_lee_dentro_de_la_carpeta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "nota.txt").write_text("contenido", encoding="utf-8")
        assert FileReader(base).run("nota.txt") == "contenido"


def test_leer_archivo_bloquea_rutas_fuera_de_la_carpeta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "notas"
        base.mkdir()
        try:
            FileReader(base).run("../secreto.txt")
        except ToolError:
            pass
        else:
            raise AssertionError("esperaba ToolError")


def test_toolbox_ejecuta_y_gestiona_herramienta_desconocida() -> None:
    box = ToolBox([Calculator()])
    assert box.run("calculadora", "1 + 1") == "2"
    assert "no existe" in box.run("inexistente", "")


def test_toolbox_registra_el_uso_de_una_herramienta() -> None:
    handler = _capture("assistant.tools.registry")
    try:
        ToolBox([Calculator()]).run("calculadora", "2 + 2")
    finally:
        logging.getLogger("assistant.tools.registry").removeHandler(handler)

    assert any("calculadora" in m and "2 + 2" in m for m in handler.messages)
