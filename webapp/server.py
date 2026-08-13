"""HTTP server for the Telegram Web App foundation and API."""
from __future__ import annotations

import asyncio
import json
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse

from .auth import TelegramWebAppAuthError, validate_init_data
from .bot_profile import WebAppBotProfileError, set_webapp_bot_context
from .config import WEBAPP_BOT_TOKEN, WEBAPP_HOST, WEBAPP_PORT
from .tasks_api import WebAppTaskAccessError, get_task, list_tasks


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

    def _authenticate(self):
        if not WEBAPP_BOT_TOKEN:
            raise TelegramWebAppAuthError("WEBAPP_BOT_TOKEN is not configured")
        return validate_init_data(self.headers.get("X-Telegram-Init-Data", ""), WEBAPP_BOT_TOKEN)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/health", "/healthz"}:
            self._json(200, {"status": "ok", "service": "telegram-webapp"})
            return
        try:
            user = self._authenticate()
            if path == "/api/me":
                self._json(200, {"user": user.__dict__})
                return
            if path == "/api/tasks":
                set_webapp_bot_context()
                tasks = self.server.webapp_runtime.submit(list_tasks(user.id))
                self._json(200, {"tasks": tasks})
                return
            if path.startswith("/api/tasks/"):
                set_webapp_bot_context()
                task_id = path.rsplit("/", 1)[-1]
                task = self.server.webapp_runtime.submit(get_task(user.id, task_id))
                if task is None:
                    self._json(404, {"error": "task_not_found"})
                else:
                    self._json(200, {"task": task})
                return
            self._json(404, {"error": "not_found"})
        except TelegramWebAppAuthError:
            self._json(401, {"error": "unauthorized"})
        except WebAppBotProfileError:
            self._json(500, {"error": "webapp_bot_profile_not_configured"})
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
