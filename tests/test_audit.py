"""Prueba el audit log JSONL y su integración con ToolBox."""

from __future__ import annotations

import tempfile
from pathlib import Path

from assistant.audit.jsonl_log import JsonlAuditLog
from assistant.tools.calculator import Calculator
from assistant.tools.registry import ToolBox


def test_registra_y_relee_eventos_en_orden() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = JsonlAuditLog(Path(tmp) / "activity.log")
        log.tool_used("calculadora", "1+1", "2", ok=True, ms=1.0)
        log.tool_used("reloj", "", "2026-07-20", ok=True, ms=0.5)

        eventos = log.recent(10)
        assert [e.tool for e in eventos] == ["calculadora", "reloj"]
        assert eventos[0].ok is True


def test_recent_acota_al_limite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = JsonlAuditLog(Path(tmp) / "activity.log")
        for i in range(5):
            log.tool_used("t", str(i), "ok", ok=True, ms=1.0)
        assert [e.arg for e in log.recent(2)] == ["3", "4"]


def test_los_eventos_sobreviven_entre_sesiones() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "activity.log"
        JsonlAuditLog(path).tool_used("calculadora", "2*2", "4", ok=True, ms=1.0)
        # Nueva instancia sobre el mismo fichero.
        assert JsonlAuditLog(path).recent(10)[0].tool == "calculadora"


def test_toolbox_escribe_en_el_audit_log() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = JsonlAuditLog(Path(tmp) / "activity.log")
        ToolBox([Calculator()], audit=log).run("calculadora", "3*3")

        eventos = log.recent(10)
        assert len(eventos) == 1
        assert eventos[0].tool == "calculadora" and eventos[0].result == "9"
