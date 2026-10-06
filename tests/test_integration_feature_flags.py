from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import integrations


@pytest.mark.asyncio
async def test_google_tasks_is_hidden_when_feature_is_disabled(monkeypatch):
    service = SimpleNamespace(connected=AsyncMock(return_value=False))
    monkeypatch.setattr(integrations, "integration_service", service)
    profile = SimpleNamespace(
        feature_enabled=lambda name: name != "google_tasks",
    )
    context = SimpleNamespace(bot_data={"bot_config": profile})

    markup = await integrations.integrations_keyboard("42", "bot-a", context=context)
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert "🪟 Microsoft To Do" in labels
    assert "🔵 Google Tasks" not in labels


@pytest.mark.asyncio
async def test_disabled_google_tasks_callback_is_rejected(monkeypatch):
    service = SimpleNamespace(start_oauth=AsyncMock())
    monkeypatch.setattr(integrations, "integration_service", service)
    profile = SimpleNamespace(
        key="bot-a",
        feature_enabled=lambda name: name != "google_tasks",
    )
    context = SimpleNamespace(bot_data={"bot_config": profile})
    query = SimpleNamespace(
        data="int_connect_google",
        answer=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42),
    )

    await integrations.integration_callback(update, context)

    service.start_oauth.assert_not_awaited()
    query.message.reply_text.assert_awaited_once()
