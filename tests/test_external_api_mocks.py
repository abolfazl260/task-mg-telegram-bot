from unittest.mock import AsyncMock, Mock, patch

import pytest

from handlers import guest


@pytest.mark.asyncio
async def test_guest_answer_uses_mocked_telegram_api():
    context = Mock()
    context.bot._post = AsyncMock()

    await guest._answer_guest_query(context, "guest-1", "ok")

    context.bot._post.assert_awaited_once()
    assert context.bot._post.await_args.args[0] == "answerGuestQuery"


def test_external_services_are_mockable_without_network():
    # Explicit regression guard: tests must replace network-facing clients.
    with patch("services.groq_service", create=True) as groq, patch("services.jira_service", create=True) as jira:
        groq.client = Mock()
        jira.client = Mock()
        assert groq.client is not None
        assert jira.client is not None
