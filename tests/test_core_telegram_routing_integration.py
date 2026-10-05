from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import menu
from handlers import start as start_handler
from handlers import task as task_handler
from services import task_service


class FakeMessage:
    def __init__(self, chat_id=100, text=""):
        self.chat_id = chat_id
        self.text = text
        self.reply_text = AsyncMock()
        self.edit_text = AsyncMock()


class FakeQuery:
    def __init__(self, data, message=None):
        self.data = data
        self.message = message or FakeMessage()
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class FakeBot:
    def __init__(self):
        self._post = AsyncMock(side_effect=self._post_impl)

    async def _post_impl(self, method, data=None):
        if method == "sendRichMessage":
            return SimpleNamespace(message_id=501)
        return SimpleNamespace(message_id=(data or {}).get("message_id", 501))


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot_data = {}
        self.args = []
        self.bot = FakeBot()


def fake_update(*, user_id=42, text="", callback_data=None):
    user = SimpleNamespace(
        id=user_id,
        first_name="Test",
        last_name="User",
        full_name="Test User",
        username="tester",
    )
    message = FakeMessage(chat_id=777, text=text)
    query = FakeQuery(callback_data, message) if callback_data is not None else None
    return SimpleNamespace(
        effective_user=user,
        effective_chat=SimpleNamespace(id=777),
        effective_message=message,
        message=message,
        callback_query=query,
    )


@pytest.mark.asyncio
async def test_start_handler_executes_real_start_flow(monkeypatch):
    update = fake_update()
    context = FakeContext()

    monkeypatch.setattr(start_handler, "main_menu_summary", lambda user_id: "summary")
    monkeypatch.setattr(start_handler, "main_menu", lambda context: "menu-markup")

    await start_handler.start(update, context)

    context.bot._post.assert_awaited_once()
    method, = context.bot._post.await_args.args
    assert method == "sendRichMessage"
    update.message.reply_text.assert_awaited_once()
    assert "summary" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_add_command_handler_enters_title_state():
    update = fake_update()
    context = FakeContext()

    await task_handler.add_task(update, context)

    assert context.user_data["step"] == "title"
    assert context.user_data["new_task"] == {}
    assert context.user_data["create_task_user_id"] == 42
    context.bot._post.assert_awaited_once()
    assert context.bot._post.await_args.args[0] == "sendRichMessage"


@pytest.mark.asyncio
async def test_manual_add_callback_routes_to_same_create_flow():
    update = fake_update(callback_data="add_task_manual")
    context = FakeContext()

    await menu.button_handler(update, context)

    assert context.user_data["step"] == "title"
    assert context.user_data["new_task"] == {}
    update.callback_query.answer.assert_awaited()
    assert context.bot._post.await_args.args[0] == "sendRichMessage"


@pytest.mark.asyncio
async def test_priority_deadline_category_and_tag_callbacks_advance_state(monkeypatch):
    context = FakeContext()
    context.user_data.update(
        {
            "new_task": {"title": "Core routing task"},
            "step": "priority",
            "create_task_message_id": 501,
            "create_task_user_id": 42,
        }
    )

    priority_update = fake_update(callback_data="priority_high")
    await task_handler.priority_selected(priority_update, context)
    assert context.user_data["new_task"]["priority"] == "high"
    assert context.user_data["step"] == "deadline"

    monkeypatch.setattr(
        task_handler,
        "_category_options",
        AsyncMock(return_value=["Work", "Personal"]),
    )
    deadline_update = fake_update(callback_data="deadline_none")
    await task_handler.deadline_selected(deadline_update, context)
    assert context.user_data["new_task"]["deadline"] == ""
    assert context.user_data["step"] == "category"

    from handlers import tag_suggestions_legacy

    monkeypatch.setattr(
        tag_suggestions_legacy,
        "recent_tag_keyboard",
        AsyncMock(return_value=(None, ["urgent"])),
    )
    category_update = fake_update(callback_data="category_pick_0")
    await task_handler.optional_field_callback(category_update, context)
    assert context.user_data["new_task"]["category"] == "Work"
    assert context.user_data["step"] == "tags"

    tag_update = fake_update(callback_data="tags_skip")
    await task_handler._handle_tag_callback(tag_update, context)
    assert context.user_data["new_task"]["tags"] == ""
    assert context.user_data["step"] == "description"


@pytest.mark.asyncio
async def test_invalid_priority_callback_does_not_advance_flow():
    update = fake_update(callback_data="priority_impossible")
    context = FakeContext()
    context.user_data.update(
        {
            "new_task": {"title": "Invalid priority"},
            "step": "priority",
            "create_task_message_id": 501,
        }
    )

    await task_handler.priority_selected(update, context)

    assert "priority" not in context.user_data["new_task"]
    assert context.user_data["step"] == "priority"
    assert update.callback_query.answer.await_count == 2
    assert update.callback_query.answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_status_callback_executes_real_service_update(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    task_id = await task_service.create_task_async(
        user_id=42,
        title="Status route",
        priority="medium",
        deadline="",
        category="",
        tags="",
        description="",
    )

    update = fake_update(callback_data=f"start_{task_id}")
    context = FakeContext()

    await task_handler.start_task(update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored["status"] == "in_progress"
    update.callback_query.edit_message_text.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_menu_callback_is_ignored_without_wrong_routing():
    update = fake_update(callback_data="completely_unknown_callback")
    context = FakeContext()

    await menu.button_handler(update, context)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.message.reply_text.assert_not_awaited()
    assert context.user_data == {}
