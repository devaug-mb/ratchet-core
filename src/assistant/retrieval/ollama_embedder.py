"""Embedder que usa el endpoint de embeddings de Ollama (local).

Reutiliza el mismo host de Ollama que el chat. El `opener` se puede inyectar para
poder probar sin red.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Callable

from assistant.retrieval.base import Embedder, EmbeddingError

logger = logging.getLogger(__name__)

Opener = Callable[..., Any]


class OllamaEmbedder(Embedder):
    def __init__(
        self,
        model: str,
        host: str,
        timeout: float,
        opener: Opener = urllib.request.urlopen,
    ) -> None:
        self._model = model
        self._url = f"{host.rstrip('/')}/api/embeddings"
        self._timeout = timeout
        self._opener = opener

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"model": self._model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise EmbeddingError(
                f"No pude generar embeddings con Ollama ({self._model}). "
                f"¿Has hecho `ollama pull {self._model}`? Detalle: {exc}"
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise EmbeddingError(f"Respuesta inválida del embedder: {exc}") from exc

        try:
            return [float(value) for value in data["embedding"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError(f"Formato de embedding inesperado: {data!r}") from exc
