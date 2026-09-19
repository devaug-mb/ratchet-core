"""Gestión de perfiles (personalidades) del asistente.

Un perfil es un fichero de prompt de texto dentro del directorio de perfiles. El
perfil activo se elige por nombre en `config.toml`; para cambiarlo, se edita la
configuración y se reinicia. Reutiliza `load_prompt` para leer el contenido.
"""

from __future__ import annotations

from pathlib import Path

from assistant.prompts import load_prompt


class ProfileNotFoundError(Exception):
    """El perfil solicitado no existe en el directorio de perfiles."""


def available(directory: Path) -> list[str]:
    """Nombres de los perfiles disponibles (ficheros `.txt`), ordenados."""
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.txt"))


def load(directory: Path, name: str) -> str:
    """Devuelve el prompt del perfil `name`.

    Lanza `ProfileNotFoundError` con la lista de perfiles disponibles si no existe.
    """
    path = directory / f"{name}.txt"
    if not path.is_file():
        disponibles = ", ".join(available(directory)) or "(ninguno)"
        raise ProfileNotFoundError(
            f"Perfil '{name}' no encontrado en {directory}. Disponibles: {disponibles}"
        )
    return load_prompt(path)
