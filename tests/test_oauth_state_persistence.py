from __future__ import annotations

import importlib
import importlib.util
from urllib.parse import parse_qs, urlparse

import pytest

from services import database, integration_service


def _prepare_database(tmp_path):
    original_path = database.DB_PATH
    database.shutdown_sync_loop()
    database._db_by_loop.clear()
    database.DB_PATH = tmp_path / "oauth-state.db"
    database.sync_execute(
        "INSERT INTO users(user_id,full_name) VALUES(?,?)",
        ("42", "OAuth User"),
    )
    return original_path


def _restore_database(original_path):
    database.shutdown_sync_loop()
    database._db_by_loop.clear()
    database.DB_PATH = original_path


def _state_from_url(url):
    return parse_qs(urlparse(url).query)["state"][0]


def _token_response():
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_in": 3600,
    }


def test_oauth_state_survives_process_restart(tmp_path, monkeypatch):
    original_path = _prepare_database(tmp_path)
    try:
        monkeypatch.setenv("INTEGRATION_REDIRECT_BASE_URL", "https://example.test")
        url = integration_service.start_oauth("google", "42", "bot-a")
        state = _state_from_url(url)

        persisted = database.sync_one(
            "oauth_pending_states", "state=?", (state,)
        )
        assert persisted is not None
        assert persisted["provider"] == "google"
        assert persisted["user_id"] == "42"
        assert persisted["bot_key"] == "bot-a"

        restarted = importlib.reload(integration_service)
        monkeypatch.setattr(restarted, "_post_form", lambda *args, **kwargs: _token_response())

        pending = restarted.complete_oauth("google", "auth-code", state)

        assert pending["user_id"] == "42"
        assert pending["bot_key"] == "bot-a"
        connection = database.sync_one(
            "external_connections",
            "user_id=? AND provider=? AND bot_key=?",
            ("42", "google", "bot-a"),
        )
        assert connection is not None
        assert connection["enabled"] == 1
        assert connection["refresh_token"] == "refresh-token"
        assert database.sync_one(
            "oauth_pending_states", "state=?", (state,)
        ) is None

        with pytest.raises(ValueError, match="منقضی یا نامعتبر"):
            restarted.complete_oauth("google", "replay-code", state)
    finally:
        _restore_database(original_path)


def test_oauth_callback_can_be_handled_by_different_module_instance(tmp_path, monkeypatch):
    original_path = _prepare_database(tmp_path)
    try:
        monkeypatch.setenv("INTEGRATION_REDIRECT_BASE_URL", "https://example.test")
        url = integration_service.start_oauth("microsoft", "42", "bot-b")
        state = _state_from_url(url)

        spec = importlib.util.spec_from_file_location(
            "integration_service_instance_b",
            integration_service.__file__,
        )
        assert spec is not None and spec.loader is not None
        instance_b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(instance_b)
        monkeypatch.setattr(instance_b, "_post_form", lambda *args, **kwargs: _token_response())

        pending = instance_b.complete_oauth("microsoft", "auth-code", state)

        assert pending["provider"] == "microsoft"
        assert pending["user_id"] == "42"
        assert pending["bot_key"] == "bot-b"
        connection = database.sync_one(
            "external_connections",
            "user_id=? AND provider=? AND bot_key=?",
            ("42", "microsoft", "bot-b"),
        )
        assert connection is not None
        assert connection["enabled"] == 1
        assert database.sync_one(
            "oauth_pending_states", "state=?", (state,)
        ) is None
    finally:
        _restore_database(original_path)


def test_expired_persistent_oauth_state_is_rejected_and_consumed(tmp_path, monkeypatch):
    original_path = _prepare_database(tmp_path)
    try:
        monkeypatch.setenv("INTEGRATION_REDIRECT_BASE_URL", "https://example.test")
        now = 10_000.0
        database.sync_execute(
            "INSERT INTO oauth_pending_states(state,provider,user_id,bot_key,created_at) "
            "VALUES(?,?,?,?,?)",
            ("expired-state", "google", "42", "bot-a", now - 601),
        )
        monkeypatch.setattr(integration_service.time, "time", lambda: now)

        with pytest.raises(ValueError, match="منقضی یا نامعتبر"):
            integration_service.complete_oauth(
                "google", "auth-code", "expired-state"
            )

        assert database.sync_one(
            "oauth_pending_states", "state=?", ("expired-state",)
        ) is None
    finally:
        _restore_database(original_path)
