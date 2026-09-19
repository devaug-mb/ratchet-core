"""Registro de actividad en formato JSONL (una línea JSON por evento).

Fichero *append-only*: eficiente, no bloquea, y fácil de leer/`grep`/`tail` desde
fuera. "Listar por orden" es simplemente leer el fichero.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from assistant.audit.base import AuditEvent, AuditLog

logger = logging.getLogger(__name__)

_RESULT_LIMIT = 200


class JsonlAuditLog(AuditLog):
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def tool_used(self, tool: str, arg: str, result: str, ok: bool, ms: float) -> None:
        event = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "arg": arg,
            "result": result[:_RESULT_LIMIT],
            "ok": ok,
            "ms": round(ms, 1),
        }
        try:
            with self._path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:  # nunca debe tumbar la sesión por no poder auditar
            logger.warning("no se pudo escribir el audit log: %s", exc)

    def recent(self, limit: int) -> list[AuditEvent]:
        if not self._path.is_file():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        events: list[AuditEvent] = []
        for line in lines[-limit:]:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(
                AuditEvent(
                    timestamp=data.get("timestamp", ""),
                    tool=data.get("tool", ""),
                    arg=data.get("arg", ""),
                    result=data.get("result", ""),
                    ok=bool(data.get("ok", False)),
                    ms=float(data.get("ms", 0.0)),
                )
            )
        return events
