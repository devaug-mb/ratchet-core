"""Prueba la generación de eventos SSE y el token, con dobles (sin sockets)."""

from __future__ import annotations

import json
from collections.abc import Iterator

from assistant.commands import CommandResult
from assistant.web.server import sse_events, token_ok


class StubManager:
    def __init__(self, command: CommandResult | None = None, chunks: tuple[str, ...] = ()):
        self._command = command
        self._chunks = chunks

    def command(self, text: str) -> CommandResult | None:
        return self._command

    def reply_stream(self, chat_id: str, text: str) -> Iterator[str]:
        yield from self._chunks


def _decode(frames: list[bytes]) -> list[dict]:
    events = []
    for frame in frames:
        line = frame.decode("utf-8").strip()
        assert line.startswith("data:")
        events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_sse_transmite_la_respuesta_por_trozos() -> None:
    frames = list(sse_events(StubManager(chunks=("Hola", ", Gus")), "c1", "hola"))
    events = _decode(frames)
    assert events[0]["chunk"] == "Hola"
    assert events[1]["chunk"] == ", Gus"
    assert events[-1]["done"] is True


def test_sse_devuelve_el_resultado_de_un_comando() -> None:
    frames = list(sse_events(StubManager(command=CommandResult("ayuda…")), "c1", "/help"))
    events = _decode(frames)
    assert events[0]["chunk"] == "ayuda…"
    assert events[-1]["done"] is True


def test_token_ok_sin_token_configurado_permite_todo() -> None:
    assert token_ok("", None) is True
    assert token_ok("", "cualquier cosa") is True


def test_token_ok_exige_coincidencia() -> None:
    assert token_ok("secreto", "Bearer secreto") is True
    assert token_ok("secreto", "secreto") is True
    assert token_ok("secreto", "Bearer otro") is False
    assert token_ok("secreto", None) is False
