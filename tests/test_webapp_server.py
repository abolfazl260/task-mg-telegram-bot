from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

from webapp.auth import TelegramWebAppAuthError
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



def test_protected_dashboard_is_hidden_until_authentication():
    server, thread = _start_server()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/", timeout=2
        ) as response:
            html = response.read().decode("utf-8")
        assert 'data-auth-protected hidden' in html
        assert '/static/auth-guard.js' in html

        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/static/auth-guard.js", timeout=2
        ) as response:
            guard = response.read().decode("utf-8")
        assert "برای استفاده از این بخش باید از طریق تلگرام احراز هویت شوید" in guard
        assert "response.status === 401" in guard
        assert "response.status === 403" in guard
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_anonymous_api_request_returns_401(monkeypatch):
    monkeypatch.setattr(
        "webapp.server.get_webapp_bot_profile",
        lambda _bot_key: SimpleNamespace(
            feature_enabled=lambda _name: True,
            permission_enabled=lambda _name: True,
        ),
    )

    def reject_anonymous(_init_data, _bot_key):
        raise TelegramWebAppAuthError("Missing Telegram Web App authentication data")

    monkeypatch.setattr("webapp.server.authenticate_telegram_request", reject_anonymous)

    server, thread = _start_server()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/me"
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            assert json.loads(exc.read()) == {"error": "unauthorized"}
        else:
            raise AssertionError("Expected HTTP 401")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_expired_telegram_session_returns_401(monkeypatch):
    monkeypatch.setattr(
        "webapp.server.get_webapp_bot_profile",
        lambda _bot_key: SimpleNamespace(
            feature_enabled=lambda _name: True,
            permission_enabled=lambda _name: True,
        ),
    )

    def reject_expired(_init_data, _bot_key):
        raise TelegramWebAppAuthError("Expired Telegram Web App authentication data")

    monkeypatch.setattr("webapp.server.authenticate_telegram_request", reject_expired)

    server, thread = _start_server()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/me",
            headers={"X-Telegram-Init-Data": "expired"},
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            assert json.loads(exc.read()) == {"error": "unauthorized"}
        else:
            raise AssertionError("Expected HTTP 401")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_authenticated_user_without_permission_returns_403(monkeypatch):
    monkeypatch.setattr(
        "webapp.server.get_webapp_bot_profile",
        lambda _bot_key: SimpleNamespace(
            feature_enabled=lambda _name: True,
            permission_enabled=lambda _name: False,
        ),
    )
    monkeypatch.setattr(
        "webapp.server.authenticate_telegram_request",
        lambda _init_data, _bot_key: SimpleNamespace(id=42, first_name="User"),
    )

    server, thread = _start_server()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/tasks",
            headers={"X-Telegram-Init-Data": "valid"},
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
            assert json.loads(exc.read()) == {"error": "forbidden"}
        else:
            raise AssertionError("Expected HTTP 403")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
