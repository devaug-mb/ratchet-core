"""Carga de configuración.

Único módulo que lee `config.toml`. El resto del código recibe un objeto
`Config` ya construido, sin saber de dónde vino.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Parámetros del asistente."""

    model: str
    host: str
    timeout: float
    retries: int
    max_turns: int
    profile: str
    profiles_dir: Path
    files_dir: Path
    max_tool_iterations: int
    memory_db_path: Path
    memory_max_facts: int
    organizer_db_path: Path
    retrieval_enabled: bool
    embed_model: str
    retrieval_index_path: Path
    retrieval_top_k: int
    retrieval_chunk_size: int
    audit_enabled: bool
    audit_file: Path
    web_host: str
    web_port: int
    web_token: str
    log_level: str
    log_file: Path | None

    @classmethod
    def load(cls, path: Path) -> "Config":
        with path.open("rb") as file:
            data = tomllib.load(file)
        base = path.resolve().parent
        llm = data["llm"]
        conversation = data.get("conversation", {})
        profile = data.get("profile", {})
        tools = data.get("tools", {})
        memory = data.get("memory", {})
        organizer = data.get("organizer", {})
        retrieval = data.get("retrieval", {})
        audit = data.get("audit", {})
        web = data.get("web", {})
        logging_cfg = data.get("logging", {})
        log_file = logging_cfg.get("file")
        return cls(
            model=llm["model"],
            host=llm["host"],
            timeout=float(llm.get("timeout", 60.0)),
            retries=int(llm.get("retries", 1)),
            max_turns=int(conversation.get("max_turns", 10)),
            profile=profile.get("active", "system"),
            profiles_dir=base / profile.get("directory", "prompts"),
            files_dir=base / tools.get("files_dir", "notes"),
            max_tool_iterations=int(tools.get("max_iterations", 3)),
            memory_db_path=base / memory.get("db_path", "data/memory.db"),
            memory_max_facts=int(memory.get("max_facts", 20)),
            organizer_db_path=base / organizer.get("db_path", "data/organizer.db"),
            retrieval_enabled=bool(retrieval.get("enabled", True)),
            embed_model=retrieval.get("embed_model", "nomic-embed-text"),
            retrieval_index_path=base / retrieval.get("index_db", "data/notes_index.db"),
            retrieval_top_k=int(retrieval.get("top_k", 3)),
            retrieval_chunk_size=int(retrieval.get("chunk_size", 800)),
            audit_enabled=bool(audit.get("enabled", True)),
            audit_file=base / audit.get("file", "data/activity.log"),
            web_host=web.get("host", "127.0.0.1"),
            web_port=int(web.get("port", 8000)),
            web_token=str(web.get("token", "")),
            log_level=logging_cfg.get("level", "INFO"),
            log_file=(base / log_file) if log_file else None,
        )
