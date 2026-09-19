"""Arranca la interfaz web: `python -m assistant.web`.

Reutiliza los mismos builders y comprobación de salud que el CLI; solo cambia la
"cara" (web en vez de consola).
"""

from __future__ import annotations

from assistant import logging_setup
from assistant.config import Config
from assistant.llm.base import LLMError
from assistant.main import (
    CONFIG_PATH,
    build_brief,
    build_data,
    build_provider,
    build_session_manager,
    build_stores,
)
from assistant.profiles import ProfileNotFoundError
from assistant.web.server import run_server


def main() -> None:
    config = Config.load(CONFIG_PATH)
    logging_setup.configure(level=config.log_level, file=config.log_file)

    provider = build_provider(config)
    try:
        provider.check_health()
        stores = build_stores(config)
        manager = build_session_manager(config, provider, stores)
        data = build_data(config, stores)
        brief = build_brief(provider, data)
    except (LLMError, ProfileNotFoundError) as exc:
        print(f"No se puede iniciar: {exc}")
        return

    run_server(
        manager,
        data,
        brief,
        config.web_host,
        config.web_port,
        config.profile,
        config.web_token,
    )


if __name__ == "__main__":
    main()
