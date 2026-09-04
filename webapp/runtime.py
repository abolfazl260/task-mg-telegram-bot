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
    from .report_routes import add_monthly_web_button, handle_report_api, handle_report_get, web_report_html
    from .public_tasks import handle_public_task_api, handle_public_task_get
    from .report_tokens import resolve_report_token
    from .report_routes import _html
    from handlers import reports as reports_handler
    from urllib.parse import quote, urlparse

    original_get = WebAppHandler.do_GET
    original_post = WebAppHandler.do_POST
    original_patch = WebAppHandler.do_PATCH

    def do_get(self):
        if handle_public_task_get(self):
            return
        if handle_public_task_api(self):
            return
        path = urlparse(self.path).path
        if path and path not in ('/', '/report-launch') and not path.startswith('/api/') and '/' not in path.strip('/') and len(path.strip('/')) >= 40:
            token = path.strip('/')
            if resolve_report_token(token):
                html = web_report_html(token)
                task_url = f'/tasks/{quote(token, safe="")}'
                nav = f'<a href="{task_url}" style="display:inline-flex;align-items:center;justify-content:center;text-decoration:none;border-radius:12px;padding:10px 14px;background:#ffffff18;border:1px solid #ffffff30;color:#fff;font-weight:800;font-size:13px;white-space:nowrap">📋 مدیریت تسک‌ها</a>'
                html = html.replace('<div class="hero-top">', f'<div class="hero-top">{nav}', 1)
                _html(self, 200, html)
                return
        if handle_report_get(self):
            return
        if handle_report_api(self):
            return
        return original_get(self)

    def do_post(self):
        if handle_public_task_api(self):
            return
        return original_post(self)

    def do_patch(self):
        if handle_public_task_api(self):
            return
        return original_patch(self)

    WebAppHandler.do_GET = do_get
    WebAppHandler.do_POST = do_post
    WebAppHandler.do_PATCH = do_patch

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
