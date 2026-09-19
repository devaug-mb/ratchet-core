"""Configuración central de logging.

Único sitio que configura el logging del asistente. El resto de módulos solo hacen
`logging.getLogger(__name__)` y emiten mensajes; no configuran nada.
"""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def configure(level: str = "INFO", file: Path | None = None) -> None:
    """Configura el logging a consola y, opcionalmente, a un fichero."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(file, encoding="utf-8"))

    logging.basicConfig(
        level=level.upper(),
        format=_FORMAT,
        datefmt=_DATEFMT,
        handlers=handlers,
    )
