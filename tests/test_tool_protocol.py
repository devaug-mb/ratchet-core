"""Prueba la detección del marcador de herramientas."""

from __future__ import annotations

from assistant.core.tool_protocol import parse_tool_call


def test_detecta_una_llamada_a_herramienta() -> None:
    call = parse_tool_call("[[tool:calculadora]] 2 + 2")
    assert call is not None
    assert call.name == "calculadora"
    assert call.arg == "2 + 2"


def test_sin_marcador_devuelve_none() -> None:
    assert parse_tool_call("una respuesta normal sin herramientas") is None


def test_detecta_el_marcador_aunque_haya_texto_alrededor() -> None:
    call = parse_tool_call("Voy a calcular: [[tool:calculadora]] 3*3")
    assert call is not None
    assert call.name == "calculadora"
    assert call.arg == "3*3"


def test_acepta_el_argumento_dentro_de_los_corchetes() -> None:
    call = parse_tool_call("[[tool:leer_archivo ejemplo.txt]]")
    assert call is not None
    assert call.name == "leer_archivo"
    assert call.arg == "ejemplo.txt"


def test_acepta_herramienta_sin_argumento() -> None:
    call = parse_tool_call("[[tool:reloj]]")
    assert call is not None
    assert call.name == "reloj"
    assert call.arg == ""


def test_limpia_comillas_del_argumento() -> None:
    call = parse_tool_call('[[tool:leer_archivo]] "ejemplo.txt"')
    assert call is not None
    assert call.arg == "ejemplo.txt"
