"""Herramienta de lectura de archivos de texto.

Lee archivos SOLO dentro de una carpeta base configurada. Cualquier ruta que
intente salir de esa carpeta se rechaza, de modo que el modelo no puede leer
ficheros arbitrarios del sistema.
"""

from __future__ import annotations

from pathlib import Path

from assistant.tools.base import Tool, ToolError


class FileReader(Tool):
    name = "leer_archivo"
    description = (
        "Lee un archivo de texto de la carpeta de notas. "
        "Argumento: ruta relativa del archivo, p. ej. 'ideas.txt'."
    )

    def __init__(self, base_dir: Path, max_chars: int = 20000) -> None:
        self._base = base_dir.resolve()
        self._max_chars = max_chars

    def run(self, arg: str) -> str:
        rel = arg.strip().strip("\"'")
        if not rel:
            raise ToolError("indica la ruta del archivo a leer.")

        target = (self._base / rel).resolve()
        if not target.is_relative_to(self._base):
            raise ToolError("la ruta está fuera de la carpeta de notas.")
        if not target.is_file():
            raise ToolError(f"no existe el archivo '{rel}'.")

        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > self._max_chars:
            text = text[: self._max_chars] + "\n...(contenido truncado)"
        return text
