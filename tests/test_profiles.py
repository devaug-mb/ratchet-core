"""Prueba la gestión de perfiles con un directorio temporal (sin tocar el real)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from assistant import profiles
from assistant.profiles import ProfileNotFoundError


def _crear_perfiles(directory: Path) -> None:
    (directory / "system.txt").write_text("prompt general", encoding="utf-8")
    (directory / "aleman.txt").write_text("tutor de aleman", encoding="utf-8")


def test_available_lista_los_perfiles_ordenados() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _crear_perfiles(directory)
        assert profiles.available(directory) == ["aleman", "system"]


def test_available_sin_directorio_devuelve_lista_vacia() -> None:
    assert profiles.available(Path("/directorio/que/no/existe")) == []


def test_load_devuelve_el_contenido_del_perfil() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _crear_perfiles(directory)
        assert profiles.load(directory, "aleman") == "tutor de aleman"


def test_load_perfil_inexistente_lanza_error_con_disponibles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _crear_perfiles(directory)
        try:
            profiles.load(directory, "italiano")
        except ProfileNotFoundError as exc:
            mensaje = str(exc)
            assert "italiano" in mensaje
            assert "aleman" in mensaje  # sugiere los disponibles
        else:
            raise AssertionError("esperaba ProfileNotFoundError")
