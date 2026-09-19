"""Registro de herramientas disponibles, indexadas por nombre."""

from __future__ import annotations

import logging
import time

from assistant.audit.base import AuditLog
from assistant.tools.base import Tool, ToolError

logger = logging.getLogger(__name__)

_LOG_RESULT_LIMIT = 80


def _short(text: str) -> str:
    """Acorta un texto para que el log quepa en una línea."""
    text = text.replace("\n", " ")
    if len(text) > _LOG_RESULT_LIMIT:
        return text[:_LOG_RESULT_LIMIT] + "…"
    return text


class ToolBox:
    """Contiene las herramientas y las ejecuta por nombre de forma segura."""

    def __init__(
        self, tools: list[Tool] | None = None, audit: AuditLog | None = None
    ) -> None:
        self._tools: dict[str, Tool] = {tool.name: tool for tool in (tools or [])}
        self._audit = audit

    def __len__(self) -> int:
        return len(self._tools)

    def describe(self) -> str:
        """Lista las herramientas en texto, para incluirlas en el prompt."""
        return "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools.values()
        )

    def run(self, name: str, arg: str) -> str:
        """Ejecuta la herramienta `name`.

        Devuelve siempre texto (también en caso de error) para poder reinyectarlo
        en la conversación. Un fallo de una herramienta nunca tumba la sesión. Cada
        invocación se registra en el log (nombre, argumento, resultado y duración).
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("herramienta desconocida: %r", name)
            result = f"Error: no existe la herramienta '{name}'."
            self._audit_event(name, arg, result, ok=False, ms=0.0)
            return result

        start = time.perf_counter()
        try:
            result = tool.run(arg)
        except ToolError as exc:
            ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "herramienta '%s' arg=%r -> error: %s (%.0f ms)", name, arg, exc, ms
            )
            result = f"Error: {exc}"
            self._audit_event(name, arg, result, ok=False, ms=ms)
            return result
        except Exception as exc:  # defensivo
            ms = (time.perf_counter() - start) * 1000
            logger.exception("herramienta '%s' arg=%r fallo inesperado", name, arg)
            result = f"Error inesperado en '{name}': {exc}"
            self._audit_event(name, arg, result, ok=False, ms=ms)
            return result

        ms = (time.perf_counter() - start) * 1000
        logger.info(
            "herramienta '%s' arg=%r -> %r (%.0f ms)", name, arg, _short(result), ms
        )
        self._audit_event(name, arg, result, ok=True, ms=ms)
        return result

    def _audit_event(self, name: str, arg: str, result: str, ok: bool, ms: float) -> None:
        if self._audit is not None:
            self._audit.tool_used(name, arg, result, ok, ms)
