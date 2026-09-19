"""Prueba el resumen diario con un proveedor y unos datos falsos."""

from __future__ import annotations

from datetime import date

from assistant.brief import DailyBrief
from assistant.llm.base import LLMProvider, Message


class FakeProvider(LLMProvider):
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def generate(self, messages: list[Message]) -> str:
        self.messages = messages
        return "  Buenos días. Tienes clase de alemán y un par de cosas. "


class FakeData:
    def schedule_today(self) -> list[dict]:
        return [{"id": 1, "title": "reunión", "kind": "dated", "start": "10:00", "end": "14:00"}]

    def items(self, list_name: str | None = None) -> list[dict]:
        return [
            {"id": 1, "list": "compra", "text": "pan", "done": False},
            {"id": 2, "list": "compra", "text": "leche", "done": True},
        ]

    def review_due(self, subject: str | None = None) -> list[dict]:
        return [{"id": 1, "subject": "alemán", "text": "der Tisch", "next_review": "x"}]


class EmptyData:
    def schedule_today(self) -> list[dict]:
        return []

    def items(self, list_name: str | None = None) -> list[dict]:
        return []

    def review_due(self, subject: str | None = None) -> list[dict]:
        return []


def test_el_brief_pasa_los_datos_al_modelo_y_limpia_la_respuesta() -> None:
    provider = FakeProvider()
    brief = DailyBrief(provider, FakeData())

    salida = brief.generate()

    assert salida == "Buenos días. Tienes clase de alemán y un par de cosas."
    contexto = provider.messages[-1].content
    assert "reunión" in contexto  # de la agenda de hoy
    assert "de 10:00 a 14:00" in contexto  # con rango de horas
    assert "pan" in contexto  # tarea pendiente
    assert "leche" not in contexto  # la hecha no cuenta
    assert "der Tisch" in contexto  # repaso


def test_el_brief_sin_datos_no_llama_al_modelo() -> None:
    provider = FakeProvider()
    salida = DailyBrief(provider, EmptyData()).generate()

    assert "nada" in salida.lower()
    assert provider.messages == []  # ni siquiera se consultó al modelo
