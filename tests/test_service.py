"""Prueba la capa de servicio: distingue comandos de mensajes y delega la respuesta."""

from __future__ import annotations

from pathlib import Path

from assistant.commands import build_commands
from assistant.core.conversation import Conversation
from assistant.items.sqlite_store import SqliteItemStore
from assistant.llm.base import LLMProvider, Message
from assistant.memory.sqlite_store import SqliteMemoryStore
from assistant.service import AssistantService


class FakeProvider(LLMProvider):
    def generate(self, messages: list[Message]) -> str:
        return "respuesta del modelo"


def _service() -> AssistantService:
    conversation = Conversation(FakeProvider())
    commands = build_commands(
        "system",
        Path("prompts"),
        SqliteMemoryStore(Path(":memory:")),
        SqliteItemStore(Path(":memory:")),
    )
    return AssistantService(conversation, commands)


def test_command_devuelve_none_para_un_mensaje_normal() -> None:
    assert _service().command("¿qué tal?") is None


def test_command_ejecuta_un_comando() -> None:
    resultado = _service().command("/help")
    assert resultado is not None
    assert "Comandos disponibles" in resultado.output


def test_reply_stream_genera_la_respuesta() -> None:
    respuesta = "".join(_service().reply_stream("hola"))
    assert respuesta == "respuesta del modelo"
