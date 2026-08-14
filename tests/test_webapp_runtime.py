from __future__ import annotations

import os

import webapp.runtime as runtime


def test_webapp_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WEBAPP_ENABLED", raising=False)
    assert runtime.webapp_enabled() is False


def test_webapp_enabled_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("WEBAPP_ENABLED", value)
        assert runtime.webapp_enabled() is True


def test_start_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("WEBAPP_ENABLED", raising=False)
    assert runtime.start_webapp_server() is None
    assert runtime._server is None


def test_start_and_stop_server(monkeypatch):
    monkeypatch.setenv("WEBAPP_ENABLED", "true")
    monkeypatch.setenv("WEBAPP_HOST", "127.0.0.1")
    monkeypatch.setenv("WEBAPP_PORT", "0")

    server = runtime.start_webapp_server()
    try:
        assert server is not None
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_address[1] > 0
        assert runtime.start_webapp_server() is server
    finally:
        runtime.stop_webapp_server()

    assert runtime._server is None
    assert runtime._thread is None
