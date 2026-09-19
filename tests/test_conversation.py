"""Prueba el dominio inyectando un proveedor falso: sin Ollama, sin red."""

from __future__ import annotations

from pathlib import Path

from assistant.core.conversation import Conversation
from assistant.llm.base import LLMProvider, Message, Role
from assistant.memory.base import MemoryStore
from assistant.tools.base import Tool
from assistant.tools.calculator import Calculator
from assistant.tools.registry import ToolBox


class FakeMemory(MemoryStore):
    def __init__(self, facts: dict[str, str] | None = None) -> None:
        self._facts = dict(facts or {})

    def remember(self, key: str, value: str) -> None:
        self._facts[key] = value

    def all(self) -> dict[str, str]:
        return dict(self._facts)

    def forget(self, key: str) -> None:
        self._facts.pop(key, None)


class FakeProvider(LLMProvider):
    """Registra una copia de los mensajes recibidos en cada llamada."""

    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []

    def generate(self, messages: list[Message]) -> str:
        self.calls.append(list(messages))  # copia: Conversation seguirá mutando la suya
        return self.reply


class ScriptedProvider(LLMProvider):
    """Devuelve respuestas de una lista en orden; repite la última al agotarse."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[Message]] = []

    def generate(self, messages: list[Message]) -> str:
        self.calls.append(list(messages))
        if len(self._replies) > 1:
            return self._replies.pop(0)
        return self._replies[0]


class ChunkProvider(LLMProvider):
    """Emite respuestas por trozos. `responses` es una lista de respuestas, cada
    una una lista de fragmentos; se avanza en cada llamada y se repite la última."""

    def __init__(self, responses: list[list[str]]) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def _advance(self) -> list[str]:
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]

    def generate(self, messages: list[Message]) -> str:
        self.calls.append(list(messages))
        return "".join(self._advance())

    def stream(self, messages: list[Message]):
        self.calls.append(list(messages))
        for chunk in self._advance():
            yield chunk


class _EchoTool(Tool):
    name = "eco"
    description = "devuelve el argumento tal cual"

    def run(self, arg: str) -> str:
        return arg


def test_send_devuelve_la_respuesta_del_proveedor() -> None:
    conversation = Conversation(FakeProvider("hola"))
    assert conversation.send("¿qué tal?") == "hola"


def test_send_envia_el_texto_como_mensaje_de_usuario() -> None:
    provider = FakeProvider()
    Conversation(provider).send("pregunta")

    ultima_llamada = provider.calls[-1]
    assert len(ultima_llamada) == 1
    assert ultima_llamada[0].role is Role.USER
    assert ultima_llamada[0].content == "pregunta"


def test_mantiene_el_historial_entre_turnos() -> None:
    provider = FakeProvider("respuesta-1")
    conversation = Conversation(provider)

    conversation.send("primero")
    conversation.send("segundo")

    # En el segundo turno debe enviarse: usuario-1, asistente-1, usuario-2.
    segunda_llamada = provider.calls[-1]
    assert [(m.role, m.content) for m in segunda_llamada] == [
        (Role.USER, "primero"),
        (Role.ASSISTANT, "respuesta-1"),
        (Role.USER, "segundo"),
    ]


def test_antepone_el_prompt_de_sistema() -> None:
    provider = FakeProvider()
    conversation = Conversation(provider, system_prompt="Eres un asistente de prueba.")

    conversation.send("hola")

    enviado = provider.calls[-1]
    assert enviado[0].role is Role.SYSTEM
    assert enviado[0].content == "Eres un asistente de prueba."
    assert enviado[1].role is Role.USER


def test_el_prompt_de_sistema_sobrevive_al_recorte() -> None:
    provider = FakeProvider()
    conversation = Conversation(
        provider, max_turns=1, system_prompt="prompt-persistente"
    )

    conversation.send("viejo")
    conversation.send("nuevo")

    enviado = provider.calls[-1]
    # Sistema + 1 turno recortado (2 mensajes) = 3 mensajes.
    assert enviado[0].role is Role.SYSTEM
    assert enviado[0].content == "prompt-persistente"
    assert all(m.content != "viejo" for m in enviado)
    assert enviado[-1].content == "nuevo"


def test_recorta_el_historial_al_superar_max_turns() -> None:
    provider = FakeProvider()
    conversation = Conversation(provider, max_turns=1)  # límite: 2 mensajes

    conversation.send("viejo")
    conversation.send("nuevo")

    # El turno más antiguo ("viejo") debe haberse descartado.
    segunda_llamada = provider.calls[-1]
    assert len(segunda_llamada) == 2
    assert all(m.content != "viejo" for m in segunda_llamada)
    assert segunda_llamada[-1].content == "nuevo"


def test_ejecuta_una_herramienta_y_responde_con_el_resultado() -> None:
    provider = ScriptedProvider(["[[tool:calculadora]] 2 + 2", "Son 4."])
    conversation = Conversation(provider, tools=ToolBox([Calculator()]))

    respuesta = conversation.send("¿cuánto es 2 + 2?")

    assert respuesta == "Son 4."
    # La segunda llamada al modelo debe incluir el resultado de la herramienta.
    texto = " ".join(m.content for m in provider.calls[-1])
    assert "resultado de calculadora" in texto
    assert "4" in texto


def test_sin_herramientas_no_interpreta_marcadores() -> None:
    provider = ScriptedProvider(["[[tool:calculadora]] 2+2"])
    conversation = Conversation(provider)  # sin ToolBox

    # El marcador se devuelve tal cual, sin ejecutar nada.
    assert conversation.send("hola") == "[[tool:calculadora]] 2+2"


def test_inyecta_los_hechos_recordados_en_el_sistema() -> None:
    provider = FakeProvider()
    conversation = Conversation(provider, memory=FakeMemory({"nombre": "Alba"}))

    conversation.send("hola")

    primero = provider.calls[-1][0]
    assert primero.role is Role.SYSTEM
    assert "Alba" in primero.content


def test_sin_hechos_no_anade_bloque_de_memoria() -> None:
    provider = FakeProvider()
    conversation = Conversation(provider, memory=FakeMemory())

    conversation.send("hola")

    # Sin prompt, sin tools y sin hechos: no hay mensaje de sistema.
    assert provider.calls[-1][0].role is Role.USER


def test_acota_los_hechos_inyectados_en_el_prompt() -> None:
    facts = {f"clave{i}": str(i) for i in range(10)}
    provider = FakeProvider()
    conversation = Conversation(
        provider, memory=FakeMemory(facts), memory_max_facts=3
    )

    conversation.send("hola")

    system = provider.calls[-1][0].content
    # El bloque de memoria no debe contener más de los 3 hechos permitidos.
    lineas_de_hechos = [ln for ln in system.splitlines() if ln.startswith("- clave")]
    assert len(lineas_de_hechos) == 3


def test_send_stream_emite_la_respuesta_por_trozos() -> None:
    provider = ChunkProvider([["Hola", ", ", "Gus"]])
    conversation = Conversation(provider)

    trozos = list(conversation.send_stream("hola"))

    assert trozos == ["Hola", ", ", "Gus"]


def test_send_stream_guarda_la_respuesta_en_el_historial() -> None:
    provider = ChunkProvider([["respuesta"]])
    conversation = Conversation(provider)

    list(conversation.send_stream("uno"))
    list(conversation.send_stream("dos"))

    contenidos = [m.content for m in provider.calls[-1]]
    assert "respuesta" in contenidos


def test_send_delega_en_send_stream() -> None:
    provider = ChunkProvider([["a", "b", "c"]])
    assert Conversation(provider).send("hola") == "abc"


def test_streaming_no_muestra_el_marcador_de_herramienta() -> None:
    provider = ChunkProvider(
        [
            ["[[tool:", "calculadora]] ", "2 + 2"],  # 1ª respuesta: llamada a tool
            ["Son ", "4."],  # respuesta final
        ]
    )
    conversation = Conversation(provider, tools=ToolBox([Calculator()]))

    mostrado = "".join(conversation.send_stream("¿cuánto es 2 + 2?"))

    assert "tool:" not in mostrado
    assert mostrado == "Son 4."


def test_streaming_oculta_marcador_aunque_haya_texto_antes() -> None:
    # El modelo narra y LUEGO emite un marcador: el marcador no debe mostrarse.
    provider = ChunkProvider(
        [
            ["Voy a mirar ", "tus notas.\n", "[[tool:eco]] hola"],
            ["Aquí está."],
        ]
    )
    conversation = Conversation(provider, tools=ToolBox([_EchoTool()]))

    mostrado = "".join(conversation.send_stream("qué tengo"))

    assert "[[tool" not in mostrado
    assert "Aquí está." in mostrado


def test_ejecuta_varias_herramientas_de_una_respuesta() -> None:
    from assistant.items.sqlite_store import SqliteItemStore
    from assistant.tools.organizer import AddItemTool

    store = SqliteItemStore(Path(":memory:"))
    provider = ChunkProvider(
        [
            ["[[tool:agregar_item]] compra: pan\n[[tool:agregar_item]] compra: leche"],
            ["Hecho."],
        ]
    )
    conversation = Conversation(provider, tools=ToolBox([AddItemTool(store)]))

    "".join(conversation.send_stream("añade pan y leche"))

    assert [i.text for i in store.items("compra")] == ["pan", "leche"]


def test_streaming_sin_tools_muestra_texto_con_corchetes() -> None:
    # Sin herramientas no se oculta nada, aunque parezca un marcador.
    provider = ChunkProvider([["[[tool:x]] literal"]])
    conversation = Conversation(provider)

    assert "".join(conversation.send_stream("hola")) == "[[tool:x]] literal"


def test_respeta_el_tope_de_iteraciones_de_herramientas() -> None:
    # El modelo pide herramienta siempre: no debe colgarse.
    provider = ScriptedProvider(["[[tool:eco]] hola"])
    conversation = Conversation(
        provider, tools=ToolBox([_EchoTool()]), max_tool_iterations=3
    )

    conversation.send("dispara el bucle")

    # 3 iteraciones + 1 generación final = 4 llamadas al modelo, y termina.
    assert len(provider.calls) == 4
