"""Capa de servicio: el núcleo reutilizable del asistente.

Encapsula "recibe texto -> comando o respuesta" sin saber nada de la interfaz
(consola, web, voz...). El CLI actual es solo un cliente delgado de este servicio;
en el futuro podría haber otros que reutilicen exactamente esta clase.
"""

from __future__ import annotations

from collections.abc import Iterator

from assistant.commands import CommandRegistry, CommandResult
from assistant.core.conversation import Conversation


class AssistantService:
    """Procesa comandos y genera respuestas. No hace entrada/salida."""

    def __init__(self, conversation: Conversation, commands: CommandRegistry) -> None:
        self._conversation = conversation
        self._commands = commands

    def command(self, text: str) -> CommandResult | None:
        """Devuelve el resultado si `text` es un comando (`/...`), o None si no lo es."""
        return self._commands.dispatch(text)

    def reply_stream(self, user_text: str) -> Iterator[str]:
        """Genera la respuesta del asistente a un mensaje, en fragmentos."""
        return self._conversation.send_stream(user_text)
