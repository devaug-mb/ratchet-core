"""Herramienta de reloj: fecha y hora actuales."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from assistant.tools.base import Tool


class Clock(Tool):
    name = "reloj"
    description = "Devuelve la fecha y hora actuales. No necesita argumento."

    def __init__(self, now: Callable[[], datetime] = datetime.now) -> None:
        # `now` se inyecta para poder fijar la hora en los tests.
        self._now = now

    def run(self, arg: str) -> str:
        return self._now().strftime("%Y-%m-%d %H:%M:%S")
