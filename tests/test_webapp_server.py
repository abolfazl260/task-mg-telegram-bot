from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from webapp.server import WebAppHandler, ThreadingHTTPServer


def _start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_health_endpoint():
    server, thread = _start_server()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/health", timeout=2
        ) as response:
            assert response.status == 200
            assert response.headers["Content-Type"].startswith("application/json")
            payload = json.loads(response.read())
            assert payload == {"status": "ok", "service": "telegram-webapp"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unknown_endpoint_returns_404():
    server, thread = _start_server()
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/missing", timeout=2
            )
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("Expected HTTP 404")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
