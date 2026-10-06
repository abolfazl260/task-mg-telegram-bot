from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import task as task_handler
from services import database, task_service


class FakeMessage:
    def __init__(self, *, chat_id: int = 777, text: str = "") -> None:
        self.chat_id = chat_id
        self.text = text
        self.caption = ""
        self.photo = []
        self.voice = None
        self.audio = None
        self.document = None
        self.video = None
        self.sticker = None
        self.animation = None
        self.contact = None
        self.location = None
        self.reply_text = AsyncMock()
        self.edit_text = AsyncMock()
        self.reply_photo = AsyncMock()
        self.reply_voice = AsyncMock()
        self.reply_audio = AsyncMock()
        self.reply_document = AsyncMock()
        self.reply_video = AsyncMock()
        self.reply_sticker = AsyncMock()
        self.reply_animation = AsyncMock()


class FakeQuery:
    def __init__(self, data: str, message: FakeMessage | None = None) -> None:
        self.data = data
        self.message = message or FakeMessage()
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class FakeBot:
    def __init__(self) -> None:
        self._post = AsyncMock(return_value=SimpleNamespace(message_id=501))
        self.send_message = AsyncMock()


class FakeContext:
    def __init__(self) -> None:
        self.user_data = {}
        self.bot_data = {}
        self.bot = FakeBot()


def fake_update(
    *,
    user_id: int = 42,
    callback_data: str | None = None,
    text: str = "",
):
    user = SimpleNamespace(
        id=user_id,
        first_name="Test",
        last_name="User",
        full_name="Test User",
        username=f"user{user_id}",
    )
    message = FakeMessage(text=text)
    query = FakeQuery(callback_data, message) if callback_data is not None else None
    return SimpleNamespace(
        effective_user=user,
        effective_chat=SimpleNamespace(id=message.chat_id),
        effective_message=message,
        message=message,
        callback_query=query,
    )


async def _insert_task(
    task_id: str,
    *,
    owner_id: int = 42,
    status: str = "pending",
    assignee_id: int | None = None,
    assignee_name: str = "",
) -> None:
    await database.execute(
        "INSERT OR IGNORE INTO users(user_id,timezone,date_format,messages_count) "
        "VALUES(?,?,?,0)",
        (str(owner_id), "UTC", "jalali"),
    )
    if assignee_id is not None:
        await database.execute(
            "INSERT OR IGNORE INTO users(user_id,timezone,date_format,messages_count) "
            "VALUES(?,?,?,0)",
            (str(assignee_id), "UTC", "jalali"),
        )
    await database.execute(
        "INSERT INTO tasks("
        "id,bot_key,user_id,title,priority,status,assignee_id,assignee_name"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (
            task_id,
            "test",
            str(owner_id),
            f"Task {task_id}",
            "medium",
            status,
            str(assignee_id) if assignee_id is not None else None,
            assignee_name,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "prefix", "expected_status"),
    [
        ("start_task", "start", "in_progress"),
        ("done_task", "done", "done"),
        ("pending_task", "pending", "pending"),
        ("cancel_task", "cancel", "cancelled"),
    ],
)
async def test_status_callbacks_execute_handler_and_mutate_exact_uuid_task(
    test_db,
    handler_name,
    prefix,
    expected_status,
):
    task_id = "12345678-1234-5678-1234-567812345678"
    await _insert_task(task_id, status="in_progress" if prefix == "pending" else "pending")
    update = fake_update(callback_data=f"{prefix}_{task_id}")
    context = FakeContext()

    await getattr(task_handler, handler_name)(update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored is not None
    assert stored["status"] == expected_status
    update.callback_query.edit_message_text.assert_awaited_once()
    update.callback_query.message.reply_text.assert_awaited_once()
    update.callback_query.answer.assert_awaited()


@pytest.mark.asyncio
async def test_legacy_task_id_is_preserved_in_callback_parsing(test_db):
    task_id = "AB12CD34"
    await _insert_task(task_id)
    update = fake_update(callback_data=f"done_{task_id}")
    context = FakeContext()

    await task_handler.done_task(update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored["status"] == "done"
    assert task_id in update.callback_query.edit_message_text.await_args.args[0]


@pytest.mark.asyncio
async def test_task_details_and_history_callbacks_load_exact_uuid(test_db):
    task_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    await _insert_task(task_id)
    context = FakeContext()

    details = fake_update(callback_data=f"task_details_{task_id}")
    await task_handler.task_details_callback(details, context)

    context.bot._post.assert_awaited_once()
    rich_data = context.bot._post.await_args.kwargs["data"]
    assert task_id in rich_data["rich_message"]["markdown"]
    details.callback_query.message.reply_text.assert_awaited()

    history = fake_update(callback_data=f"asg_history_{task_id}")
    await task_handler.assignment_manage_callback(history, FakeContext())

    history.callback_query.message.reply_text.assert_awaited_once()
    assert "تاریخچه" in history.callback_query.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_comment_callback_preserves_uuid_and_comment_is_persisted(test_db):
    task_id = "11111111-2222-4333-8444-555555555555"
    await _insert_task(task_id)
    context = FakeContext()
    callback_update = fake_update(callback_data=f"comment_add_{task_id}")

    await task_handler.comment_callback(callback_update, context)

    assert context.user_data["comment_task_id"] == task_id
    assert context.user_data["step"] == "task_comment"

    comment_update = fake_update(text="integration callback comment")
    handled = await task_handler.handle_comment_input(comment_update, context)

    comments = await task_service.get_task_comments_async(task_id)
    assert handled is True
    assert len(comments) == 1
    assert comments[0]["text"] == "integration callback comment"
    assert "comment_task_id" not in context.user_data
    comment_update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_take_callback_and_confirm_assign_exact_uuid_to_actor(test_db):
    task_id = "99999999-8888-4777-8666-555555555555"
    await _insert_task(task_id)
    context = FakeContext()

    take_update = fake_update(callback_data=f"take_{task_id}")
    await task_handler.take_assignment(take_update, context)

    assert context.user_data["take_task_id"] == task_id
    take_update.callback_query.message.reply_text.assert_awaited_once()

    confirm_update = fake_update(callback_data="take_confirm")
    await task_handler.take_confirm(confirm_update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored["assignee_id"] == "42"
    assert stored["assignee_name"] == "Test User"
    assert "take_task_id" not in context.user_data
    confirm_update.callback_query.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_owner_and_remove_assignment_callbacks_execute_real_db_flow(test_db):
    task_id = "feedface-1111-4222-8333-deadbeefcafe"
    await _insert_task(
        task_id,
        assignee_id=77,
        assignee_name="Assigned User",
    )
    context = FakeContext()

    owner_update = fake_update(callback_data=f"owner_{task_id}")
    await task_handler.assignment_manage_callback(owner_update, context)

    owner_update.callback_query.message.reply_text.assert_awaited_once()
    assert "Assigned User" in owner_update.callback_query.message.reply_text.await_args.args[0]

    remove_update = fake_update(callback_data=f"asg_remove_{task_id}")
    await task_handler.assignment_manage_callback(remove_update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    history = await task_service.get_assignment_history_async(task_id)
    assert stored["assignee_id"] is None
    assert history[-1]["action"] == "removed"
    remove_update.callback_query.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_unauthorized_status_callback_cannot_mutate_task(test_db):
    task_id = "abcdefab-cdef-4abc-8def-abcdefabcdef"
    await _insert_task(task_id, owner_id=42)
    update = fake_update(user_id=99, callback_data=f"done_{task_id}")
    context = FakeContext()

    await task_handler.done_task(update, context)

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored["status"] == "pending"
    update.callback_query.edit_message_text.assert_not_awaited()
    assert update.callback_query.answer.await_count == 2
    assert update.callback_query.answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_unauthorized_assignment_callbacks_fail_before_context_or_mutation(test_db):
    task_id = "12341234-5678-4abc-8def-1234567890ab"
    await _insert_task(task_id, owner_id=42)
    context = FakeContext()

    take_update = fake_update(user_id=99, callback_data=f"take_{task_id}")
    await task_handler.take_assignment(take_update, context)
    assert "take_task_id" not in context.user_data
    assert "مجاز" in take_update.callback_query.message.reply_text.await_args.args[0]

    owner_update = fake_update(user_id=99, callback_data=f"owner_{task_id}")
    await task_handler.assignment_manage_callback(owner_update, context)
    assert "دسترسی" in owner_update.callback_query.message.reply_text.await_args.args[0]

    change_update = fake_update(user_id=99, callback_data=f"chg_start_{task_id}")
    await task_handler.assignment_manage_callback(change_update, context)
    assert "change_task_id" not in context.user_data
    assert "مجاز" in change_update.callback_query.message.reply_text.await_args.args[0]

    stored = await task_service.get_task_by_id_async(task_id)
    assert stored["assignee_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("callback_data", "handler_name"),
    [
        ("start_missing-task", "start_task"),
        ("task_details_missing-task", "task_details_callback"),
        ("comment_add_missing-task", "comment_callback"),
        ("take_missing-task", "take_assignment"),
        ("owner_missing-task", "assignment_manage_callback"),
    ],
)
async def test_invalid_or_unknown_task_callbacks_fail_safely(
    test_db,
    callback_data,
    handler_name,
):
    update = fake_update(callback_data=callback_data)
    context = FakeContext()

    await getattr(task_handler, handler_name)(update, context)

    update.callback_query.answer.assert_awaited()
    assert (
        update.callback_query.message.reply_text.await_count
        + update.callback_query.edit_message_text.await_count
        >= 1
    )
