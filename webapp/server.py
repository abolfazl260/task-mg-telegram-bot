"""Minimal HTTP server for the Telegram Web App foundation."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
PORT = int(os.getenv("WEBAPP_PORT", "8081"))


class WebAppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/health", "/healthz"}:
            body = b'{"status":"ok","service":"telegram-webapp"}'
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
    return ThreadingHTTPServer((HOST, PORT), WebAppHandler)


def run() -> None:
    server = create_server()
    print(f"Telegram Web App server listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
