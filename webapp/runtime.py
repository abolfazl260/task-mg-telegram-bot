"""Optional runtime integration for the Telegram Web App server."""
from __future__ import annotations

import os
import threading
from typing import Optional

from .server import WebAppHTTPServer, create_server

_server: Optional[WebAppHTTPServer] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def webapp_enabled() -> bool:
    return os.getenv("WEBAPP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def start_webapp_server() -> Optional[WebAppHTTPServer]:
    global _server, _thread
    if not webapp_enabled():
        return None
    with _lock:
        if _server is not None:
            return _server
        _server = create_server()
        _thread = threading.Thread(target=_server.serve_forever, name="telegram-webapp", daemon=True)
        _thread.start()
        return _server


def stop_webapp_server() -> None:
    global _server, _thread
    with _lock:
        server, thread = _server, _thread
        _server = None
        _thread = None
    if server is not None:
        server.shutdown()
        runtime = getattr(server, "webapp_runtime", None)
        if runtime is not None:
            runtime.stop()
        server.server_close()
    if thread is not None:
        thread.join(timeout=2)
