import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_integration_handler_logs_failure_without_exposing_exception(monkeypatch, caplog):
    from handlers import integrations

    update = MagicMock()
    update.effective_user.id = 42
    query = MagicMock()
    query.data = "int_connect_google"
    query.answer = AsyncMock()
    query.message.reply_text = AsyncMock()
    update.callback_query = query

    context = MagicMock()
    context.bot_data = {}

    secret = "secret-provider-token"
    monkeypatch.setattr(
        integrations.integration_service,
        "start_oauth",
        AsyncMock(side_effect=RuntimeError(secret)),
    )

    caplog.set_level(logging.ERROR, logger=integrations.__name__)
    await integrations.integration_callback(update, context)

    query.message.reply_text.assert_awaited_once()
    user_message = query.message.reply_text.await_args.args[0]
    assert secret not in user_message
    assert "جزئیات خطا ثبت شد" in user_message
    assert "operation=start_oauth" in caplog.text
    assert "provider=google" in caplog.text
    assert "user_id=42" in caplog.text


@pytest.mark.asyncio
async def test_jira_credential_delete_failure_is_logged(monkeypatch, caplog):
    from handlers import jira

    update = MagicMock()
    update.effective_user.id = 77
    update.effective_message.text = "credential-value"
    update.effective_message.delete = AsyncMock(side_effect=RuntimeError("telegram delete failed"))
    update.effective_message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {"jira_connect": {}}

    caplog.set_level(logging.ERROR, logger=jira.__name__)
    result = await jira.jira_credential(update, context)

    assert result == jira.JIRA_PROJECT
    assert context.user_data["jira_connect"]["credential"] == "credential-value"
    assert "jira_credential_message_delete_failed" in caplog.text
    assert "user_id=77" in caplog.text
    assert "credential-value" not in caplog.text


@pytest.mark.asyncio
async def test_invalid_task_comment_payload_is_logged_without_payload(monkeypatch, caplog):
    from services import task_service

    bad_payload = "{not-json"
    monkeypatch.setattr(
        task_service,
        "fetch_all",
        AsyncMock(
            return_value=[
                {
                    "id": 9,
                    "task_id": "task-123",
                    "author_id": "42",
                    "author_name": "User",
                    "author_username": "",
                    "created_at": "2026-10-05 10:00",
                    "content_json": bad_payload,
                }
            ]
        ),
    )

    caplog.set_level(logging.WARNING, logger=task_service.__name__)
    comments = await task_service.get_task_comments_async("task-123")

    assert comments[0]["author_id"] == "42"
    assert "task_comment_content_invalid" in caplog.text
    assert "task_id=task-123" in caplog.text
    assert "comment_id=9" in caplog.text
    assert bad_payload not in caplog.text


@pytest.mark.asyncio
async def test_database_close_failure_is_logged(monkeypatch, caplog):
    from services import database

    failing_db = MagicMock()
    failing_db.close = AsyncMock(side_effect=RuntimeError("close failed"))
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(database, "_db_by_loop", {loop: failing_db})

    caplog.set_level(logging.ERROR, logger=database.__name__)
    await database.close_all_dbs()

    assert "database_close_failed" in caplog.text
    assert "operation=close_all_dbs" in caplog.text
