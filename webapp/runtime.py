"""Optional runtime integration for the Telegram Web App server.

The Web App is disabled by default so importing this module cannot change the
existing bot runtime. The main application can explicitly call
``start_webapp_server()`` when ``WEBAPP_ENABLED=true``.
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from .server import ThreadingHTTPServer, create_server

_server: Optional[ThreadingHTTPServer] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def webapp_enabled() -> bool:
    return os.getenv("WEBAPP_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def start_webapp_server() -> Optional[ThreadingHTTPServer]:
    """Start the Web App once when explicitly enabled.

    Returns the running server, or ``None`` when the feature is disabled.
    A daemon thread keeps the Web App isolated from the bot's async runtime.
    """
    global _server, _thread
    if not webapp_enabled():
        return None

    with _lock:
        if _server is not None:
            return _server
        _server = create_server()
        _thread = threading.Thread(
            target=_server.serve_forever,
            name="telegram-webapp",
            daemon=True,
        )
        _thread.start()
        return _server


def stop_webapp_server() -> None:
    """Stop the Web App server if it was started by this module."""
    global _server, _thread
    with _lock:
        server, thread = _server, _thread
        _server = None
        _thread = None

    if server is not None:
        server.shutdown()
        server.server_close()
    if thread is not None:
        thread.join(timeout=2)
