"""HTTP server for the Telegram Web App foundation and API."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import WEBAPP_HOST, WEBAPP_PORT


class WebAppHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/health", "/healthz"}:
            self._json(200, {"status": "ok", "service": "telegram-webapp"})
            return
        if path == "/api/me":
            self._json(501, {"error": "api_not_ready"})
            return
        if path == "/api/tasks" or path.startswith("/api/tasks/"):
            self._json(501, {"error": "api_not_ready"})
            return
        self._json(404, {"error": "not_found"})

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
