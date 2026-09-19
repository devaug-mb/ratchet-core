"""Resumen diario ("brief"): un saludo breve con lo importante de hoy.

Reúne los datos del día (horario de hoy, tareas pendientes, repasos) y le pide al
modelo un resumen corto y cercano. Es lo que hace que el Home se sienta vivo: te da
algo antes de que preguntes. No inventa: solo resume lo que hay en los datos.
"""

from __future__ import annotations

from assistant.data import DataView
from assistant.llm.base import LLMProvider, Message, Role

_SYSTEM = (
    "Eres el asistente personal del usuario. Con sus datos de hoy, escribe un "
    "saludo BREVE (1-2 frases), cercano y útil, que resuma lo importante. No "
    "inventes nada que no esté en los datos. Si algo está vacío, no lo menciones."
)


def _when(event: dict) -> str:
    if event.get("end"):
        return f"de {event['start']} a {event['end']}"
    return f"a las {event['start']}"


class DailyBrief:
    def __init__(self, provider: LLMProvider, data: DataView) -> None:
        self._provider = provider
        self._data = data

    def _context(self) -> str:
        parts: list[str] = []

        today = self._data.schedule_today()
        if today:
            parts.append(
                "Hoy en la agenda: "
                + "; ".join(f"{e['title']} {_when(e)}" for e in today)
            )
        pending = [item for item in self._data.items() if not item["done"]]
        if pending:
            parts.append(
                "Tareas pendientes: "
                + "; ".join(f"{i['text']} [{i['list']}]" for i in pending[:12])
            )
        reviews = self._data.review_due()
        if reviews:
            parts.append(
                "Para repasar hoy: "
                + "; ".join(f"{r['text']} [{r['subject']}]" for r in reviews[:12])
            )
        return "\n".join(parts)

    def generate(self) -> str:
        context = self._context()
        if not context:
            return "No tienes nada apuntado para hoy. ¿En qué te ayudo?"
        messages = [
            Message(role=Role.SYSTEM, content=_SYSTEM),
            Message(role=Role.USER, content=f"Mis datos de hoy:\n{context}"),
        ]
        return self._provider.generate(messages).strip()
