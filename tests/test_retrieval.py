"""Prueba la búsqueda semántica con un embedder falso (sin red)."""

from __future__ import annotations

import json
import tempfile
import urllib.error
from pathlib import Path

from assistant.retrieval.base import Embedder, EmbeddingError
from assistant.retrieval.note_index import NoteIndex, chunk_text, cosine
from assistant.retrieval.ollama_embedder import OllamaEmbedder
from assistant.tools.base import ToolError
from assistant.tools.search_notes import SearchNotesTool


class FakeEmbedder(Embedder):
    """Embedding trivial de 3 dimensiones según el tema del texto."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        lowered = text.lower()
        return [
            float("gato" in lowered or "felino" in lowered),
            float("perro" in lowered or "canino" in lowered),
            float("pez" in lowered or "acuario" in lowered),
        ]


def _notes_dir(tmp: str) -> Path:
    directory = Path(tmp)
    (directory / "gatos.txt").write_text("Los gatos son felinos domésticos.", encoding="utf-8")
    (directory / "perros.txt").write_text("El perro es un canino muy leal.", encoding="utf-8")
    return directory


# --- utilidades ---------------------------------------------------------------

def test_cosine_mide_parecido() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_chunk_divide_por_parrafos() -> None:
    text = "a" * 10 + "\n\n" + "b" * 10
    chunks = chunk_text(text, max_chars=15)
    assert len(chunks) == 2


# --- índice -------------------------------------------------------------------

def test_search_devuelve_el_fragmento_mas_parecido() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index = NoteIndex(_notes_dir(tmp), FakeEmbedder(), Path(":memory:"))
        resultados = index.search("cuéntame algo sobre el gato", k=1)
        assert len(resultados) == 1
        assert resultados[0].source == "gatos.txt"


def test_indexado_incremental_no_reembebe_sin_cambios() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        embedder = FakeEmbedder()
        index = NoteIndex(_notes_dir(tmp), embedder, Path(":memory:"))

        index.search("gato", k=1)
        llamadas_tras_primera = embedder.calls

        index.search("gato", k=1)
        # La segunda búsqueda solo embebe la consulta, no re-embebe las notas.
        assert embedder.calls - llamadas_tras_primera == 1


# --- herramienta --------------------------------------------------------------

def test_tool_buscar_notas_devuelve_fragmentos() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index = NoteIndex(_notes_dir(tmp), FakeEmbedder(), Path(":memory:"))
        salida = SearchNotesTool(index, k=1).run("gato")
        assert "gatos.txt" in salida


def test_tool_buscar_notas_arg_vacio() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index = NoteIndex(_notes_dir(tmp), FakeEmbedder(), Path(":memory:"))
        try:
            SearchNotesTool(index).run("   ")
        except ToolError:
            pass
        else:
            raise AssertionError("esperaba ToolError")


# --- embedder de Ollama (con opener falso) ------------------------------------

def test_ollama_embedder_parsea_la_respuesta() -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode("utf-8")

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    embedder = OllamaEmbedder(
        "nomic-embed-text", "http://localhost:11434", 1.0, opener=lambda *a, **k: FakeResponse()
    )
    assert embedder.embed("hola") == [0.1, 0.2, 0.3]


def test_ollama_embedder_avisa_si_falla() -> None:
    def failing_opener(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError("sin conexión")

    embedder = OllamaEmbedder("nomic-embed-text", "http://localhost:11434", 1.0, opener=failing_opener)
    try:
        embedder.embed("hola")
    except EmbeddingError as exc:
        assert "ollama pull nomic-embed-text" in str(exc)
    else:
        raise AssertionError("esperaba EmbeddingError")
