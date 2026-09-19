"""Carga de prompts desde ficheros de texto.

Único módulo que lee los ficheros de prompt. El dominio recibe el texto ya
cargado, sin saber de dónde vino.
"""

from __future__ import annotations

from pathlib import Path


def load_prompt(path: Path) -> str:
    """Devuelve el contenido de un prompt de texto UTF-8, sin espacios sobrantes."""
    return path.read_text(encoding="utf-8").strip()
