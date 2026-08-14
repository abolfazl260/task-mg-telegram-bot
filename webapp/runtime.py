"""Optional runtime integration for the Telegram Web App server."""
from __future__ import annotations

import os
import threading
from typing import Optional

from .server import WebAppHTTPServer, WebAppHandler, create_server

_server: Optional[WebAppHTTPServer] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()
_report_routes_installed = False


def webapp_enabled() -> bool:
    return os.getenv("WEBAPP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _install_report_routes() -> None:
    """Patch the existing lightweight server without changing its core API."""
    global _report_routes_installed
    if _report_routes_installed:
        return
    from .report_routes import add_monthly_web_button, handle_report_api, handle_report_get
    from handlers import reports as reports_handler

    original_get = WebAppHandler.do_GET

    def do_get(self):
        if handle_report_get(self):
            return
        if handle_report_api(self):
            return
        return original_get(self)

    WebAppHandler.do_GET = do_get

    original_reports_menu = reports_handler.reports_menu_keyboard

    def reports_menu_keyboard_with_web():
        return add_monthly_web_button(original_reports_menu())

    reports_handler.reports_menu_keyboard = reports_menu_keyboard_with_web
    _report_routes_installed = True


def start_webapp_server() -> Optional[WebAppHTTPServer]:
    global _server, _thread
    if not webapp_enabled():
        return None
    with _lock:
        if _server is not None:
            return _server
        _install_report_routes()
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
