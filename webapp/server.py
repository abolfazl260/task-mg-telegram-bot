"""HTTP server for the Telegram Web App foundation and API."""
from __future__ import annotations

import asyncio
import json
import mimetypes
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

from .api import authenticate_telegram_request
from .auth import TelegramWebAppAuthError
from .bot_profile import WebAppBotProfileError
from .config import WEBAPP_HOST, WEBAPP_PORT
from .tasks_api import WebAppTaskAccessError, get_task, list_tasks

STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebAppAsyncRuntime:
    """Own one long-lived event loop for all Web App service calls."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._run, name="telegram-webapp-async", daemon=True)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self) -> None:
        self.thread.start()

    def submit(self, coroutine) -> object:
        future: Future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        return future.result()

    def stop(self) -> None:
        if self.loop.is_closed():
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


class WebAppHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bot_key(self) -> str:
        query = parse_qs(urlparse(self.path).query)
        return (query.get("bot_key") or [""])[0].strip()

    def _authenticate(self, bot_key: str):
        return authenticate_telegram_request(
            self.headers.get("X-Telegram-Init-Data", ""),
            bot_key,
        )

    def _serve_static(self, path: str) -> bool:
        relative = path.removeprefix("/static/") if path.startswith("/static/") else ""
        if path == "/":
            relative = "index.html"
        if not relative or ".." in Path(relative).parts:
            return False
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR not in target.parents and target != STATIC_DIR:
            return False
        if not target.is_file():
            return False
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/static/index.html"} or path.startswith("/static/"):
            if self._serve_static(path):
                return
            self._json(404, {"error": "not_found"})
            return
        if path in {"/health", "/healthz"}:
            self._json(200, {"status": "ok", "service": "telegram-webapp"})
            return
        try:
            bot_key = self._bot_key()
            user = self._authenticate(bot_key)
            if path == "/api/me":
                self._json(200, {"user": user.__dict__, "bot_key": bot_key})
                return
            if path == "/api/tasks":
                tasks = self.server.webapp_runtime.submit(list_tasks(user.id, bot_key))
                self._json(200, {"tasks": tasks})
                return
            if path.startswith("/api/tasks/"):
                task_id = path.rsplit("/", 1)[-1]
                task = self.server.webapp_runtime.submit(get_task(user.id, task_id, bot_key))
                if task is None:
                    self._json(404, {"error": "task_not_found"})
                else:
                    self._json(200, {"task": task})
                return
            self._json(404, {"error": "not_found"})
        except TelegramWebAppAuthError:
            self._json(401, {"error": "unauthorized"})
        except WebAppBotProfileError:
            self._json(400, {"error": "invalid_bot_profile"})
        except WebAppTaskAccessError:
            self._json(403, {"error": "forbidden"})
        except Exception:
            self._json(500, {"error": "internal_server_error"})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Telegram-Init-Data")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


class WebAppHTTPServer(ThreadingHTTPServer):
    webapp_runtime: WebAppAsyncRuntime


def create_server() -> WebAppHTTPServer:
    server = WebAppHTTPServer((WEBAPP_HOST, WEBAPP_PORT), WebAppHandler)
    server.webapp_runtime = WebAppAsyncRuntime()
    server.webapp_runtime.start()
    return server


def run() -> None:
    server = create_server()
    print(f"Telegram Web App server listening on {WEBAPP_HOST}:{WEBAPP_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.webapp_runtime.stop()
        server.server_close()


if __name__ == "__main__":
    run()
