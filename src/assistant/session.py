"""Gestión de varias conversaciones a la vez (chats), cada una con su perfil.

Hasta ahora había UNA conversación (un perfil, un historial). Para el móvil se
quieren varias abiertas a la vez. La clave: los almacenes persistentes (memoria,
notas, tareas...) son COMPARTIDOS y globales; lo único que se multiplica es la
conversación (su perfil + su historial en RAM).

Los chats viven en memoria: se pierden al reiniciar. Persistirlos es una mejora
futura. Siempre existe un chat "por defecto" (con el perfil de config.toml) que usa
el endpoint simple `/api/v1/chat` y los clientes que no manejan varios chats (voz).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import uuid4

from assistant.commands import CommandRegistry, CommandResult
from assistant.core.conversation import Conversation

ConversationFactory = Callable[[str], Conversation]


@dataclass
class ChatSession:
    """Un chat abierto: su id, su perfil, su conversación y un título para la lista."""

    id: str
    profile: str
    conversation: Conversation
    title: str


class SessionManager:
    def __init__(
        self,
        make_conversation: ConversationFactory,
        commands: CommandRegistry,
        default_profile: str,
        list_profiles: Callable[[], list[str]],
    ) -> None:
        self._make = make_conversation
        self._commands = commands
        self._list_profiles = list_profiles
        self._sessions: dict[str, ChatSession] = {}
        self._default_id = self.create(default_profile).id

    def create(self, profile: str) -> ChatSession:
        """Abre un chat nuevo con un perfil. Lanza ProfileNotFoundError si no existe."""
        conversation = self._make(profile)  # valida el perfil al cargar su prompt
        chat_id = uuid4().hex[:8]
        session = ChatSession(chat_id, profile, conversation, title=profile)
        self._sessions[chat_id] = session
        return session

    @property
    def default_id(self) -> str:
        return self._default_id

    def get(self, chat_id: str) -> ChatSession | None:
        return self._sessions.get(chat_id)

    def list(self) -> list[ChatSession]:
        return list(self._sessions.values())

    def delete(self, chat_id: str) -> bool:
        """Cierra un chat. No permite borrar el chat por defecto."""
        if chat_id == self._default_id:
            return False
        return self._sessions.pop(chat_id, None) is not None

    def profiles(self) -> list[str]:
        return self._list_profiles()

    def command(self, text: str) -> CommandResult | None:
        """Los comandos son globales (operan sobre los almacenes compartidos)."""
        return self._commands.dispatch(text)

    def reply_stream(self, chat_id: str, text: str) -> Iterator[str]:
        """Respuesta del chat indicado, en fragmentos. KeyError si el chat no existe."""
        session = self._sessions.get(chat_id)
        if session is None:
            raise KeyError(chat_id)
        if session.title == session.profile and text.strip():
            session.title = text.strip()[:40]  # el primer mensaje da título al chat
        return session.conversation.send_stream(text)
