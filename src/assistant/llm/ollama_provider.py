"""Implementación de `LLMProvider` para Ollama (API nativa).

Es el ÚNICO módulo que conoce Ollama. Traduce entre el contrato del dominio
(`Message`) y los endpoints `/api/chat` y `/api/tags`. Usa solo la librería
estándar. El `opener` (por defecto `urllib.request.urlopen`) se puede inyectar para
poder probar sin red.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

from assistant.llm.base import LLMError, LLMProvider, Message

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = 0.5

Opener = Callable[..., Any]


class OllamaProvider(LLMProvider):
    """Habla con un servidor Ollama local vía HTTP."""

    def __init__(
        self,
        model: str,
        host: str,
        timeout: float,
        retries: int = 1,
        opener: Opener = urllib.request.urlopen,
        backoff: float = _BACKOFF_SECONDS,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout
        self._retries = retries
        self._opener = opener
        self._backoff = backoff

    # --- comprobación de estado -------------------------------------------------

    def check_health(self) -> None:
        request = urllib.request.Request(f"{self._host}/api/tags", method="GET")
        try:
            with self._opener(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LLMError(
                f"No se pudo contactar con Ollama en {self._host}. "
                "¿Está en marcha? Arráncalo con `ollama serve`."
            ) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LLMError(f"Respuesta inesperada de Ollama al comprobar el estado: {exc}") from exc

        models = {str(item.get("name", "")) for item in data.get("models", [])}
        if self._model in models or any(name.startswith(self._model) for name in models):
            return
        disponibles = ", ".join(sorted(models)) or "(ninguno)"
        raise LLMError(
            f"El modelo '{self._model}' no está disponible en Ollama. "
            f"Descárgalo con `ollama pull {self._model}`. Disponibles: {disponibles}"
        )

    # --- generación -------------------------------------------------------------

    def generate(self, messages: list[Message]) -> str:
        start = time.perf_counter()
        response = self._open_with_retry(self._payload(messages, stream=False))
        try:
            with response:
                body = json.loads(response.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LLMError(f"Respuesta inválida de Ollama: {exc}") from exc

        try:
            answer = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Formato de respuesta inesperado: {body!r}") from exc

        ms = (time.perf_counter() - start) * 1000
        logger.debug(
            "LLM %s: %d mensajes -> %d chars (%.0f ms)",
            self._model,
            len(messages),
            len(answer),
            ms,
        )
        return answer

    def stream(self, messages: list[Message]) -> Iterator[str]:
        start = time.perf_counter()
        chars = 0
        response = self._open_with_retry(self._payload(messages, stream=True))
        with response:
            for line in response:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    chars += len(chunk)
                    yield chunk
                if data.get("done"):
                    break

        ms = (time.perf_counter() - start) * 1000
        logger.debug(
            "LLM %s (stream): %d mensajes -> %d chars (%.0f ms)",
            self._model,
            len(messages),
            chars,
            ms,
        )

    # --- infraestructura HTTP ---------------------------------------------------

    def _payload(self, messages: list[Message], stream: bool) -> bytes:
        data = {
            "model": self._model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            "stream": stream,
        }
        return json.dumps(data).encode("utf-8")

    def _open_with_retry(self, body: bytes) -> Any:
        request = urllib.request.Request(
            f"{self._host}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                return self._opener(request, timeout=self._timeout)
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < self._retries:
                    logger.warning(
                        "Reintento %d/%d a Ollama: %s", attempt + 1, self._retries, exc
                    )
                    time.sleep(self._backoff)
        raise LLMError(
            f"No se pudo contactar con Ollama en {self._host} "
            f"tras {self._retries + 1} intentos: {last_error}"
        ) from last_error
