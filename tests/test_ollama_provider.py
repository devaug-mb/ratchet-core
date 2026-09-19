"""Prueba el proveedor de Ollama con un `opener` falso (sin red)."""

from __future__ import annotations

import json
import urllib.error

from assistant.llm.base import LLMError
from assistant.llm.ollama_provider import OllamaProvider


class FakeResponse:
    """Imita la respuesta de urlopen: context manager con `read()` e iterable."""

    def __init__(self, text: str = "", lines: list[bytes] | None = None) -> None:
        self._text = text.encode("utf-8")
        self._lines = lines or []

    def read(self) -> bytes:
        return self._text

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._lines)


class FakeOpener:
    """Falla las primeras `fail_times` llamadas y luego devuelve `response`."""

    def __init__(self, response: FakeResponse, fail_times: int = 0) -> None:
        self.response = response
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, request: object, timeout: float | None = None) -> FakeResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise urllib.error.URLError("conexión rechazada")
        return self.response


def _provider(opener: FakeOpener, retries: int = 1) -> OllamaProvider:
    return OllamaProvider(
        model="gemma3:4b",
        host="http://localhost:11434",
        timeout=1.0,
        retries=retries,
        opener=opener,
        backoff=0.0,
    )


def test_generate_reintenta_y_acaba_devolviendo_la_respuesta() -> None:
    opener = FakeOpener(FakeResponse('{"message": {"content": "hola"}}'), fail_times=1)
    provider = _provider(opener, retries=1)

    assert provider.generate([]) == "hola"
    assert opener.calls == 2  # un fallo + un éxito


def test_generate_falla_si_se_agotan_los_reintentos() -> None:
    opener = FakeOpener(FakeResponse("{}"), fail_times=5)
    provider = _provider(opener, retries=1)

    try:
        provider.generate([])
    except LLMError:
        pass
    else:
        raise AssertionError("esperaba LLMError")
    assert opener.calls == 2  # intento inicial + 1 reintento


def test_check_health_ok_si_el_modelo_esta() -> None:
    tags = json.dumps({"models": [{"name": "gemma3:4b"}]})
    provider = _provider(FakeOpener(FakeResponse(tags)))
    provider.check_health()  # no lanza


def test_check_health_avisa_si_falta_el_modelo() -> None:
    tags = json.dumps({"models": [{"name": "otro:1b"}]})
    provider = _provider(FakeOpener(FakeResponse(tags)))

    try:
        provider.check_health()
    except LLMError as exc:
        assert "ollama pull gemma3:4b" in str(exc)
    else:
        raise AssertionError("esperaba LLMError")


def test_check_health_avisa_si_ollama_no_responde() -> None:
    provider = _provider(FakeOpener(FakeResponse(""), fail_times=5))

    try:
        provider.check_health()
    except LLMError as exc:
        assert "ollama serve" in str(exc)
    else:
        raise AssertionError("esperaba LLMError")
