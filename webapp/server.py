"""Minimal HTTP server for the Telegram Web App foundation."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import WEBAPP_HOST, WEBAPP_PORT


class WebAppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/health", "/healthz"}:
            body = json.dumps(
                {"status": "ok", "service": "telegram-webapp"},
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, "Not Found")

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
