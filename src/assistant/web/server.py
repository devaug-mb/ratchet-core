"""Servidor web local, con la librería estándar.

Sirve la PWA de chat y expone la API `/api/v1`. Delega la conversación en el
`SessionManager` (varios chats, cada uno con su perfil) y la lectura de datos en
`DataView`. Un solo usuario; las peticiones se serializan con un lock.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.parse
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from assistant.brief import DailyBrief
from assistant.data import DataView
from assistant.llm.base import LLMError
from assistant.profiles import ProfileNotFoundError
from assistant.session import ChatSession, SessionManager

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).parent
API_VERSION = 1
API = f"/api/v{API_VERSION}"

# Ficheros estáticos servidos en la raíz (la PWA), con su tipo de contenido.
_STATIC = {
    "/manifest.json": "application/manifest+json",
    "/sw.js": "application/javascript; charset=utf-8",
    "/icon.svg": "image/svg+xml",
}


def token_ok(expected: str, header: str | None) -> bool:
    """True si no hay token configurado, o si el de la cabecera coincide."""
    if not expected:
        return True
    provided = header or ""
    if provided.startswith("Bearer "):
        provided = provided[len("Bearer "):]
    return provided == expected


def _sse(data: dict[str, object]) -> bytes:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def sse_events(manager: SessionManager, chat_id: str, text: str) -> Iterator[bytes]:
    """Tramas SSE para un mensaje en un chat: comando o respuesta en streaming."""
    result = manager.command(text)
    if result is not None:
        yield _sse({"chunk": result.output})
        yield _sse({"done": True})
        return

    try:
        for chunk in manager.reply_stream(chat_id, text):
            yield _sse({"chunk": chunk})
    except KeyError:
        yield _sse({"error": "ese chat no existe"})
    except LLMError as exc:
        logger.debug("fallo del proveedor: %s", exc)
        yield _sse({"error": str(exc)})
    yield _sse({"done": True})


def _chat_json(session: ChatSession, default_id: str) -> dict[str, object]:
    return {
        "id": session.id,
        "profile": session.profile,
        "title": session.title,
        "is_default": session.id == default_id,
    }


class AssistantHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        manager: SessionManager,
        data: DataView,
        brief: DailyBrief,
        profile: str,
        token: str = "",
    ) -> None:
        super().__init__(address, _Handler)
        self.manager = manager
        self.data = data
        self.brief = brief
        self.profile = profile
        self.token = token
        self.lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    server: AssistantHTTPServer  # type: ignore[assignment]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        logger.debug("%s - %s", self.address_string(), format % args)

    # --- GET --------------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_bytes(
                200, "text/html; charset=utf-8", (_WEB_DIR / "index.html").read_bytes()
            )
            return
        if path in _STATIC:
            self._send_bytes(200, _STATIC[path], (_WEB_DIR / path.lstrip("/")).read_bytes())
            return
        if path == f"{API}/info":  # público
            self._json(
                200,
                {
                    "api_version": API_VERSION,
                    "profile": self.server.profile,
                    "auth_required": bool(self.server.token),
                },
            )
            return
        if not path.startswith(f"{API}/"):
            self._not_found()
            return
        if not self._authorized():
            self._unauthorized()
            return
        self._route_get(path, query)

    def _route_get(self, path: str, query: dict[str, list[str]]) -> None:
        data, manager = self.server.data, self.server.manager
        first = lambda key: query.get(key, [None])[0]  # noqa: E731

        if path == f"{API}/brief":
            with self.server.lock:
                try:
                    text = self.server.brief.generate()
                except LLMError:
                    text = "¡Hola! Estoy listo para ayudarte."
            self._json(200, {"brief": text})
        elif path == f"{API}/profiles":
            self._json(200, {"profiles": manager.profiles()})
        elif path == f"{API}/chats":
            self._json(
                200,
                {"chats": [_chat_json(s, manager.default_id) for s in manager.list()]},
            )
        elif path == f"{API}/memory":
            self._json(200, {"facts": data.memory()})
        elif path == f"{API}/items":
            self._json(200, {"items": data.items(first("list"))})
        elif path == f"{API}/schedule":
            when = first("when")
            if when == "today":
                self._json(200, {"events": data.schedule_today()})
            elif when == "week":
                self._json(200, {"days": data.schedule_week()})
            else:
                self._json(200, {"entries": data.schedule_all()})
        elif path == f"{API}/review":
            self._json(200, {"due": data.review_due(first("subject"))})
        elif path == f"{API}/notes":
            self._json(200, {"notes": data.notes()})
        elif path.startswith(f"{API}/notes/"):
            name = urllib.parse.unquote(path[len(f"{API}/notes/"):])
            content = data.note(name)
            if content is None:
                self._json(404, {"error": f"no existe la nota '{name}'"})
            else:
                self._json(200, {"name": name, "content": content})
        elif path == f"{API}/activity":
            try:
                limit = int(first("limit") or 20)
            except ValueError:
                limit = 20
            self._json(200, {"events": data.activity(limit)})
        else:
            self._not_found()

    # --- POST -------------------------------------------------------------------

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._authorized():
            self._unauthorized()
            return

        if path == f"{API}/chat":
            self._chat(self.server.manager.default_id)
        elif path == f"{API}/chats":
            self._create_chat()
        elif path.startswith(f"{API}/chats/") and path.endswith("/message"):
            chat_id = path[len(f"{API}/chats/"):-len("/message")]
            self._chat(chat_id)
        else:
            self._not_found()

    def _create_chat(self) -> None:
        profile = str(self._body().get("profile", "")).strip() or self.server.profile
        try:
            session = self.server.manager.create(profile)
        except ProfileNotFoundError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, _chat_json(session, self.server.manager.default_id))

    def _chat(self, chat_id: str) -> None:
        text = str(self._body().get("message", "")).strip()
        if not text:
            self._send_bytes(400, "text/plain", b"Mensaje vacio")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with self.server.lock:
            try:
                for frame in sse_events(self.server.manager, chat_id, text):
                    self.wfile.write(frame)
                    self.wfile.flush()
            except BrokenPipeError:
                logger.debug("el cliente cerró la conexión")

    # --- DELETE -----------------------------------------------------------------

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._authorized():
            self._unauthorized()
            return
        if path.startswith(f"{API}/chats/"):
            chat_id = path[len(f"{API}/chats/"):]
            if self.server.manager.delete(chat_id):
                self._json(200, {"deleted": chat_id})
            else:
                self._json(400, {"error": "no se puede borrar (inexistente o por defecto)"})
        else:
            self._not_found()

    # --- utilidades -------------------------------------------------------------

    def _body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _authorized(self) -> bool:
        return token_ok(self.server.token, self.headers.get("Authorization"))

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", body)

    def _not_found(self) -> None:
        self._send_bytes(404, "text/plain", b"No encontrado")

    def _unauthorized(self) -> None:
        self._send_bytes(401, "text/plain", b"No autorizado")

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_server(
    manager: SessionManager,
    data: DataView,
    brief: DailyBrief,
    host: str,
    port: int,
    profile: str,
    token: str = "",
) -> None:
    server = AssistantHTTPServer((host, port), manager, data, brief, profile, token)
    url = f"http://{host}:{port}"
    logger.info("servidor web en %s (perfil: %s)", url, profile)
    auth = "con token" if token else "sin token"
    print(f"Asistente web en {url}  ({auth}, Ctrl+C para parar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
