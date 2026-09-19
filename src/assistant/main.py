"""Punto de entrada (CLI): cablea las piezas y ejecuta el bucle de conversación.

Es el "composition root" (único sitio que conoce las implementaciones concretas) y
a la vez un cliente delgado de `AssistantService`: solo hace entrada/salida por
consola; la lógica vive en el servicio y el dominio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from assistant import logging_setup, profiles
from assistant.audit.base import AuditLog
from assistant.audit.jsonl_log import JsonlAuditLog
from assistant.brief import DailyBrief
from assistant.commands import CommandRegistry, build_commands
from assistant.config import Config
from assistant.core.conversation import Conversation
from assistant.data import DataView
from assistant.items.base import ItemStore
from assistant.items.sqlite_store import SqliteItemStore
from assistant.llm.base import LLMError, LLMProvider
from assistant.llm.ollama_provider import OllamaProvider
from assistant.memory.base import MemoryStore
from assistant.memory.sqlite_store import SqliteMemoryStore
from assistant.profiles import ProfileNotFoundError
from assistant.review.base import ReviewStore
from assistant.review.sqlite_store import SqliteReviewStore
from assistant.session import ConversationFactory, SessionManager
from assistant.schedule.base import ScheduleStore
from assistant.schedule.sqlite_store import SqliteScheduleStore
from assistant.retrieval.note_index import NoteIndex
from assistant.retrieval.ollama_embedder import OllamaEmbedder
from assistant.service import AssistantService
from assistant.tools.base import Tool
from assistant.tools.calculator import Calculator
from assistant.tools.clock import Clock
from assistant.tools.file_reader import FileReader
from assistant.tools.organizer import (
    AddItemTool,
    CompleteItemTool,
    RemoveItemTool,
    ViewListTool,
)
from assistant.tools.registry import ToolBox
from assistant.tools.remember import RememberTool
from assistant.tools.review_tools import (
    AddReviewTool,
    DueReviewsTool,
    MarkReviewedTool,
)
from assistant.tools.schedule_tools import (
    AddDatedTool,
    AddWeeklyTool,
    RemoveScheduleTool,
    ViewAgendaTool,
)
from assistant.tools.search_notes import SearchNotesTool

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"
EXIT_WORDS = {"salir", "exit", "quit"}


@dataclass(frozen=True)
class Stores:
    """Los almacenes persistentes, creados una sola vez y compartidos."""

    memory: MemoryStore
    items: ItemStore
    schedule: ScheduleStore
    review: ReviewStore
    audit: AuditLog | None


def build_provider(config: Config) -> OllamaProvider:
    return OllamaProvider(
        model=config.model,
        host=config.host,
        timeout=config.timeout,
        retries=config.retries,
    )


def build_stores(config: Config) -> Stores:
    return Stores(
        memory=SqliteMemoryStore(config.memory_db_path),
        items=SqliteItemStore(config.organizer_db_path),
        schedule=SqliteScheduleStore(config.organizer_db_path),
        review=SqliteReviewStore(config.organizer_db_path),
        audit=JsonlAuditLog(config.audit_file) if config.audit_enabled else None,
    )


def build_data(config: Config, stores: Stores) -> DataView:
    return DataView(
        memory=stores.memory,
        items=stores.items,
        schedule=stores.schedule,
        review=stores.review,
        notes_dir=config.files_dir,
        audit=stores.audit,
    )


def build_tools(config: Config, stores: Stores) -> ToolBox:
    tools: list[Tool] = [
        Calculator(),
        Clock(),
        FileReader(config.files_dir),
        RememberTool(stores.memory),
        AddItemTool(stores.items),
        ViewListTool(stores.items),
        CompleteItemTool(stores.items),
        RemoveItemTool(stores.items),
        AddWeeklyTool(stores.schedule),
        AddDatedTool(stores.schedule),
        ViewAgendaTool(stores.schedule),
        RemoveScheduleTool(stores.schedule),
        AddReviewTool(stores.review),
        DueReviewsTool(stores.review),
        MarkReviewedTool(stores.review),
    ]
    if config.retrieval_enabled:
        embedder = OllamaEmbedder(config.embed_model, config.host, config.timeout)
        retriever = NoteIndex(
            config.files_dir,
            embedder,
            config.retrieval_index_path,
            chunk_size=config.retrieval_chunk_size,
        )
        tools.append(SearchNotesTool(retriever, k=config.retrieval_top_k))
    return ToolBox(tools, audit=stores.audit)


def _conversation_factory(
    config: Config, provider: LLMProvider, stores: Stores
) -> ConversationFactory:
    """Devuelve una función que crea una Conversation para un perfil dado.

    Las herramientas (`ToolBox`) se construyen UNA vez y se comparten: son sin
    estado (operan sobre los almacenes). Lo único propio de cada conversación es el
    prompt de sistema del perfil y su historial.
    """
    tools = build_tools(config, stores)

    def make(profile_name: str) -> Conversation:
        return Conversation(
            provider,
            max_turns=config.max_turns,
            system_prompt=profiles.load(config.profiles_dir, profile_name),
            tools=tools,
            max_tool_iterations=config.max_tool_iterations,
            memory=stores.memory,
            memory_max_facts=config.memory_max_facts,
        )

    return make


def _build_commands(config: Config, stores: Stores) -> CommandRegistry:
    return build_commands(
        config.profile,
        config.profiles_dir,
        stores.memory,
        stores.items,
        stores.schedule,
        stores.review,
        stores.audit,
    )


def build_service(
    config: Config, provider: LLMProvider, stores: Stores
) -> AssistantService:
    make = _conversation_factory(config, provider, stores)
    return AssistantService(make(config.profile), _build_commands(config, stores))


def build_brief(provider: LLMProvider, data: DataView) -> DailyBrief:
    return DailyBrief(provider, data)


def build_session_manager(
    config: Config, provider: LLMProvider, stores: Stores
) -> SessionManager:
    return SessionManager(
        make_conversation=_conversation_factory(config, provider, stores),
        commands=_build_commands(config, stores),
        default_profile=config.profile,
        list_profiles=lambda: profiles.available(config.profiles_dir),
    )


def _notice(message: str) -> None:
    """Mensaje dirigido al usuario (separado de los logs técnicos)."""
    print(message)


def run() -> None:
    config = Config.load(CONFIG_PATH)
    logging_setup.configure(level=config.log_level, file=config.log_file)

    provider = build_provider(config)
    try:
        provider.check_health()
        service = build_service(config, provider, build_stores(config))
    except (LLMError, ProfileNotFoundError) as exc:
        _notice(f"No se puede iniciar: {exc}")
        return

    _notice(
        f"Asistente listo (perfil: {config.profile}). "
        "Escribe /help para ver los comandos, o 'salir' para terminar."
    )
    while True:
        try:
            user_text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_text:
            continue
        if user_text.lower() in EXIT_WORDS:
            break

        result = service.command(user_text)
        if result is not None:
            _notice(result.output)
            if result.exit:
                break
            continue

        try:
            for chunk in service.reply_stream(user_text):
                print(chunk, end="", flush=True)
            print()
        except LLMError as exc:
            logger.debug("Fallo del proveedor: %s", exc)
            _notice(f"\n[No se pudo obtener respuesta: {exc}]")


if __name__ == "__main__":
    run()
