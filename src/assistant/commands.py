"""Comandos de la conversación (los que empiezan por `/`).

Framework mínimo: un registro `nombre -> función`. Cada comando recibe su argumento
(texto) y devuelve un `CommandResult` con el mensaje a mostrar y si debe terminar la
sesión. No hay motor de parsing ni jerarquías: es un diccionario de funciones.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from assistant import profiles
from assistant.audit.base import AuditLog
from assistant.items.base import ItemStore
from assistant.memory.base import MemoryStore
from assistant.review.base import ReviewStore
from assistant.schedule.agenda import week_dates, weekday_name
from assistant.schedule.base import ScheduleStore
from assistant.tools.organizer import format_items
from assistant.tools.review_tools import format_reviews
from assistant.tools.schedule_tools import format_entry


@dataclass(frozen=True)
class CommandResult:
    """Resultado de ejecutar un comando: qué mostrar y si hay que salir."""

    output: str
    exit: bool = False


CommandHandler = Callable[[str], CommandResult]


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: CommandHandler


class CommandRegistry:
    """Indexa comandos por nombre y despacha el texto de entrada."""

    def __init__(self, commands: list[Command]) -> None:
        self._commands: dict[str, Command] = {c.name: c for c in commands}
        self._commands.setdefault(
            "help",
            Command("help", "Muestra esta ayuda.", lambda _: CommandResult(self.help())),
        )

    def dispatch(self, text: str) -> CommandResult | None:
        """Ejecuta el comando del texto. Devuelve None si no es un comando (`/...`)."""
        if not text.startswith("/"):
            return None
        name, _, arg = text[1:].strip().partition(" ")
        command = self._commands.get(name.lower())
        if command is None:
            return CommandResult(f"Comando desconocido: /{name}. Escribe /help.")
        return command.handler(arg.strip())

    def help(self) -> str:
        lines = sorted(f"/{c.name} — {c.description}" for c in self._commands.values())
        return "Comandos disponibles:\n" + "\n".join(lines)


def _format_facts(facts: dict[str, str]) -> str:
    """Formatea los hechos para `/memoria`, agrupando por categoría si las hay.

    Una "categoría" es la parte de la clave antes del primer punto (`aleman.nivel`).
    Si ninguna clave usa categorías, se muestra una lista plana.
    """
    if not any("." in key for key in facts):
        lines = "\n".join(f"- {key}: {value}" for key, value in facts.items())
        return f"Datos recordados:\n{lines}"

    groups: dict[str, list[tuple[str, str]]] = {}
    for key, value in facts.items():
        category = key.split(".", 1)[0] if "." in key else "(general)"
        groups.setdefault(category, []).append((key, value))

    lines = ["Datos recordados:"]
    for category in sorted(groups):
        lines.append(f"[{category}]")
        for key, value in sorted(groups[category]):
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_commands(
    profile: str,
    profiles_dir: Path,
    memory: MemoryStore,
    items: ItemStore,
    schedule: ScheduleStore | None = None,
    review: ReviewStore | None = None,
    audit: AuditLog | None = None,
    today: Callable[[], date] = date.today,
) -> CommandRegistry:
    """Construye los comandos del asistente con sus dependencias inyectadas."""

    def cmd_perfil(_: str) -> CommandResult:
        disponibles = ", ".join(profiles.available(profiles_dir)) or "(ninguno)"
        return CommandResult(
            f"Perfil activo: {profile}. Disponibles: {disponibles}. "
            "Para cambiarlo, edita config.toml y reinicia."
        )

    def cmd_memoria(arg: str) -> CommandResult:
        facts = memory.all()
        if not facts:
            return CommandResult("No hay datos recordados.")
        if arg:  # /memoria <clave>: muestra un dato concreto
            if arg in facts:
                return CommandResult(f"{arg}: {facts[arg]}")
            return CommandResult(f"No hay ningún dato con la clave '{arg}'.")
        return CommandResult(_format_facts(facts))

    def cmd_olvidar(arg: str) -> CommandResult:
        if not arg:
            return CommandResult("Uso: /olvidar <clave>")
        if arg not in memory.all():
            return CommandResult(f"No había ningún dato con la clave '{arg}'.")
        memory.forget(arg)
        return CommandResult(f"Olvidado: {arg}")

    def cmd_lista(list_name: str) -> CommandResult:
        found = items.items(list_name)
        if not found:
            return CommandResult(f"No hay nada en '{list_name}'.")
        return CommandResult(format_items(found))

    def cmd_salir(_: str) -> CommandResult:
        return CommandResult("¡Hasta luego!", exit=True)

    commands = [
        Command("perfil", "Muestra el perfil activo y los disponibles.", cmd_perfil),
        Command(
            "memoria",
            "Lista los datos recordados (o uno: /memoria <clave>).",
            cmd_memoria,
        ),
        Command("olvidar", "Olvida un dato: /olvidar <clave>.", cmd_olvidar),
        Command("tareas", "Muestra la lista de tareas.", lambda _: cmd_lista("tareas")),
        Command("compra", "Muestra la lista de la compra.", lambda _: cmd_lista("compra")),
        Command("salir", "Termina la sesión.", cmd_salir),
    ]

    if schedule is not None:

        def cmd_horario(_: str) -> CommandResult:
            lines: list[str] = []
            for day in week_dates(today()):
                entries = schedule.on_date(day)
                if entries:
                    lines.append(f"[{weekday_name(day)} {day.isoformat()}]")
                    lines.extend(format_entry(e) for e in entries)
            if not lines:
                return CommandResult("No tienes nada esta semana.")
            return CommandResult("\n".join(lines))

        commands.append(Command("horario", "Muestra la agenda de esta semana.", cmd_horario))

    if review is not None:

        def cmd_repasar(subject: str) -> CommandResult:
            due = review.due(subject.strip().lower() or None)
            if not due:
                return CommandResult("Nada que repasar hoy.")
            return CommandResult(format_reviews(due))

        commands.append(
            Command("repasar", "Qué toca repasar hoy (opcional: /repasar <materia>).", cmd_repasar)
        )

    if audit is not None:

        def cmd_actividad(arg: str) -> CommandResult:
            try:
                limit = int(arg) if arg.strip() else 10
            except ValueError:
                limit = 10
            events = audit.recent(limit)
            if not events:
                return CommandResult("Sin actividad registrada.")
            lines = [
                f"{e.timestamp} {e.tool}({e.arg}) -> {'ok' if e.ok else 'error'} ({e.ms:.0f} ms)"
                for e in events
            ]
            return CommandResult("\n".join(lines))

        commands.append(
            Command("actividad", "Últimas herramientas usadas (opcional: /actividad <n>).", cmd_actividad)
        )

    return CommandRegistry(commands)
