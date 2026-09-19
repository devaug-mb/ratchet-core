"""Prueba el gestor de sesiones (varios chats) con dobles."""

from __future__ import annotations

from collections.abc import Iterator

from assistant.commands import CommandRegistry
from assistant.session import SessionManager


class FakeConversation:
    def __init__(self, profile: str) -> None:
        self.profile = profile

    def send_stream(self, text: str) -> Iterator[str]:
        yield f"[{self.profile}] {text}"


def _manager(profiles: tuple[str, ...] = ("system", "aleman")) -> SessionManager:
    return SessionManager(
        make_conversation=lambda profile: FakeConversation(profile),  # type: ignore[arg-type]
        commands=CommandRegistry([]),
        default_profile="system",
        list_profiles=lambda: list(profiles),
    )


def test_arranca_con_un_chat_por_defecto() -> None:
    manager = _manager()
    assert len(manager.list()) == 1
    assert manager.get(manager.default_id).profile == "system"  # type: ignore[union-attr]


def test_create_abre_un_chat_con_su_perfil() -> None:
    manager = _manager()
    session = manager.create("aleman")
    assert session.profile == "aleman"
    assert len(manager.list()) == 2


def test_reply_stream_va_al_chat_correcto() -> None:
    manager = _manager()
    session = manager.create("aleman")
    assert "".join(manager.reply_stream(session.id, "hola")) == "[aleman] hola"


def test_reply_stream_chat_inexistente_lanza_keyerror() -> None:
    manager = _manager()
    try:
        list(manager.reply_stream("nope", "x"))
    except KeyError:
        pass
    else:
        raise AssertionError("esperaba KeyError")


def test_el_primer_mensaje_titula_el_chat() -> None:
    manager = _manager()
    session = manager.create("aleman")
    assert session.title == "aleman"
    list(manager.reply_stream(session.id, "¿cómo se dice mesa?"))
    assert manager.get(session.id).title == "¿cómo se dice mesa?"  # type: ignore[union-attr]


def test_no_se_puede_borrar_el_chat_por_defecto() -> None:
    manager = _manager()
    assert manager.delete(manager.default_id) is False


def test_borra_un_chat_normal() -> None:
    manager = _manager()
    session = manager.create("aleman")
    assert manager.delete(session.id) is True
    assert manager.get(session.id) is None


def test_profiles_lista_los_disponibles() -> None:
    assert _manager().profiles() == ["system", "aleman"]
