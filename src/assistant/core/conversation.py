"""Lógica de conversación (dominio puro).

Resuelve un turno: prompt de sistema (con perfil, memoria e instrucciones de
herramientas) + historial de sesión + herramientas. `send_stream` produce la
respuesta en fragmentos para mostrarla progresivamente; `send` es su equivalente
que devuelve el texto completo. Cuando el modelo pide una herramienta, se ejecuta y
se reinyecta el resultado, hasta un tope de iteraciones; en streaming, esas
respuestas intermedias (que contienen el marcador) NO se muestran.

Conoce solo la interfaz `LLMProvider` y las abstracciones de herramientas, nunca
una implementación concreta del modelo.
"""

from __future__ import annotations

from collections.abc import Iterator

from assistant.core.tool_protocol import (
    instructions,
    marker_start,
    parse_tool_calls,
    trailing_partial_len,
)
from assistant.llm.base import LLMProvider, Message, Role
from assistant.memory.base import MemoryStore
from assistant.tools.registry import ToolBox


class Conversation:
    """Orquesta el diálogo, el historial de sesión, las herramientas y la memoria."""

    def __init__(
        self,
        provider: LLMProvider,
        max_turns: int = 10,
        system_prompt: str | None = None,
        tools: ToolBox | None = None,
        max_tool_iterations: int = 3,
        memory: MemoryStore | None = None,
        memory_max_facts: int = 20,
    ) -> None:
        self._provider = provider
        self._max_turns = max_turns
        self._system_prompt = system_prompt
        self._tools = tools
        self._max_tool_iterations = max_tool_iterations
        self._memory = memory
        self._memory_max_facts = memory_max_facts
        self._history: list[Message] = []

    def send(self, user_text: str) -> str:
        """Resuelve un turno y devuelve la respuesta completa (sin streaming)."""
        return "".join(self.send_stream(user_text))

    def send_stream(self, user_text: str) -> Iterator[str]:
        """Resuelve un turno emitiendo la respuesta final en fragmentos."""
        self._history.append(Message(role=Role.USER, content=user_text))
        self._trim()

        answer = yield from self._answer_stream()

        self._history.append(Message(role=Role.ASSISTANT, content=answer))
        self._trim()
        return answer

    def _answer_stream(self) -> Iterator[str]:
        """Consulta al modelo, resolviendo hasta `max_tool_iterations` herramientas.

        Emite (yield) solo la respuesta final; las llamadas a herramientas se
        consumen sin mostrar los marcadores. Si una respuesta pide varias
        herramientas, se ejecutan TODAS antes de volver a preguntar. Devuelve el
        texto final completo.
        """
        for _ in range(self._max_tool_iterations):
            raw = yield from self._stream_one()
            if not self._tools:
                return raw

            calls = parse_tool_calls(raw)
            if not calls:
                return raw

            self._history.append(Message(role=Role.ASSISTANT, content=raw))
            for call in calls:
                result = self._tools.run(call.name, call.arg)
                self._history.append(
                    Message(role=Role.USER, content=self._format_result(call.name, result))
                )
            self._trim()

        # Tope de herramientas encadenadas alcanzado: última respuesta.
        return (yield from self._stream_one())

    def _stream_one(self) -> Iterator[str]:
        """Transmite una respuesta del modelo y devuelve su texto completo.

        Sin herramientas, emite todo tal cual. Con herramientas, oculta cualquier
        marcador `[[tool:...]]` y todo lo que venga después: en cuanto aparece uno,
        deja de emitir (esa parte es plumbing de herramientas, no respuesta).
        """
        parts: list[str] = []
        if not self._tools:
            for chunk in self._provider.stream(self._messages()):
                parts.append(chunk)
                yield chunk
            return "".join(parts)

        emitted = 0
        marker_seen = False
        for chunk in self._provider.stream(self._messages()):
            parts.append(chunk)
            if marker_seen:
                continue
            text = "".join(parts)
            start = marker_start(text)
            if start != -1:
                marker_seen = True
                if emitted < start:
                    yield text[emitted:start]
                    emitted = start
                continue
            # Emite lo seguro, reteniendo un final que podría iniciar un marcador.
            safe = len(text) - trailing_partial_len(text)
            if safe > emitted:
                yield text[emitted:safe]
                emitted = safe

        text = "".join(parts)
        if not marker_seen and emitted < len(text):
            yield text[emitted:]
        return text

    @staticmethod
    def _format_result(name: str, result: str) -> str:
        return f"[resultado de {name}]\n{result}"

    def _messages(self) -> list[Message]:
        """Prompt de sistema (con instrucciones de tools si hay) + historial."""
        system = self._system_content()
        if system is None:
            return list(self._history)
        return [Message(role=Role.SYSTEM, content=system), *self._history]

    def _system_content(self) -> str | None:
        parts: list[str] = []
        if self._system_prompt:
            parts.append(self._system_prompt)
        remembered = self._remembered_facts()
        if remembered:
            parts.append(remembered)
        if self._tools:
            parts.append(instructions(self._tools.describe()))
        return "\n\n".join(parts) if parts else None

    def _remembered_facts(self) -> str | None:
        """Bloque de texto con los hechos guardados, o None si no hay memoria/hechos."""
        if self._memory is None:
            return None
        facts = self._memory.recent(self._memory_max_facts)
        if not facts:
            return None
        lines = "\n".join(f"- {key}: {value}" for key, value in facts.items())
        return f"Datos que recuerdas del usuario (de sesiones anteriores):\n{lines}"

    def _trim(self) -> None:
        """Conserva solo los últimos `max_turns` turnos (2 mensajes por turno).

        Opera solo sobre el historial; el prompt de sistema nunca se descarta.
        """
        limit = self._max_turns * 2
        if len(self._history) > limit:
            self._history = self._history[-limit:]
