"""HTTP server for the Telegram Web App foundation and API."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .auth import TelegramWebAppAuthError, validate_init_data
from .config import WEBAPP_HOST, WEBAPP_PORT


class WebAppHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authenticate(self):
        token = os.getenv("BOT_TOKEN", "")
        if not token:
            raise TelegramWebAppAuthError("BOT_TOKEN is not configured")
        return validate_init_data(self.headers.get("X-Telegram-Init-Data", ""), token)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/health", "/healthz"}:
            self._json(200, {"status": "ok", "service": "telegram-webapp"})
            return
        if path == "/api/me":
            try:
                user = self._authenticate()
                self._json(200, {"user": user.__dict__})
            except TelegramWebAppAuthError:
                self._json(401, {"error": "unauthorized"})
            return
        if path == "/api/tasks" or path.startswith("/api/tasks/"):
            self._json(501, {"error": "api_not_ready"})
            return
        self._json(404, {"error": "not_found"})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Telegram-Init-Data")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server() -> ThreadingHTTPServer:
    return ThreadingHTTPServer((WEBAPP_HOST, WEBAPP_PORT), WebAppHandler)


def run() -> None:
    server = create_server()
    print(f"Telegram Web App server listening on {WEBAPP_HOST}:{WEBAPP_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
