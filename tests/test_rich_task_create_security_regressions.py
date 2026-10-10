"""Regression coverage for Rich task-creation capabilities, dates and retries."""

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# Importing start installs the canonical Rich handlers on the task module.
from handlers import start as _start  # noqa: F401
from handlers import task as task_handler
from handlers import create_task_flow
from services import task_service
from services.database import fetch_all
from services.task_capabilities import (
    install_task_capabilities,
    task_creation_allowed,
    task_creation_field_enabled,
)


class FakeMessage:
    def __init__(self, text=""):
        self.chat_id = 777
        self.message_id = 501
        self.text = text
        self.reply_text = AsyncMock()
        self.delete = AsyncMock()


class FakeContext:
    def __init__(self, profile=None):
        self.user_data = {}
        self.bot_data = {"bot_config": profile} if profile is not None else {}
        self.bot = SimpleNamespace(_post=AsyncMock(return_value={"message_id": 501}))


def fake_update(*, text="", callback_data=None):
    message = FakeMessage(text)
    query = None if callback_data is None else SimpleNamespace(
        data=callback_data, message=message, answer=AsyncMock(),
    )
    user = SimpleNamespace(
        id=42, first_name="Test", last_name="User",
        full_name="Test User", username="testuser",
    )
    return SimpleNamespace(
        effective_user=user, effective_message=message,
        callback_query=query, message=message,
    )


def profile(*, disabled_features=(), denied_permissions=(), options=None):
    disabled = set(disabled_features)
    denied = set(denied_permissions)
    return SimpleNamespace(
        feature_enabled=lambda name: name not in disabled,
        permission_enabled=lambda name: name not in denied,
        settings={"task_options": dict(options or {})},
    )


@pytest.mark.parametrize(
    "field,feature,permission,option",
    [
        ("priority", "priority", "priority.set", "allow_priority"),
        ("deadline", "deadline", "deadline.set", None),
        ("category", "categories", "categories.manage", "allow_categories"),
        ("tags", "tags", "tags.manage", "allow_tags"),
        ("assignment", "assignment", "assignment.manage", "allow_assignment"),
    ],
)
def test_rich_create_capability_checks_feature_permission_and_option(
    field, feature, permission, option,
):
    assert task_creation_field_enabled(FakeContext(profile()), field)
    assert not task_creation_field_enabled(
        FakeContext(profile(disabled_features={feature})), field
    )
    assert not task_creation_field_enabled(
        FakeContext(profile(denied_permissions={permission})), field
    )
    if option is not None:
        assert not task_creation_field_enabled(
            FakeContext(profile(options={option: False})), field
        )


def test_create_permission_disabled_rejects_all_fields():
    context = FakeContext(profile(denied_permissions={"tasks.create"}))
    assert not task_creation_allowed(context)
    for field in ("priority", "deadline", "category", "tags", "assignment"):
        assert not task_creation_field_enabled(context, field)


@pytest.mark.asyncio
async def test_rich_flow_skips_all_disabled_optional_sections():
    context = FakeContext(profile(
        disabled_features={"priority", "deadline", "categories", "tags", "assignment"}
    ))
    await task_handler.add_task(fake_update(), context)
    assert uuid.UUID(context.user_data["new_task"]["_create_request_id"])

    await task_handler.save_task(fake_update(text="A permitted task"), context)
    assert context.user_data["step"] == "description"
    assert context.user_data["new_task"]["priority"] == "medium"
    assert context.user_data["new_task"]["deadline"] == ""
    assert context.user_data["new_task"]["category"] == ""
    assert context.user_data["new_task"]["tags"] == ""

    await task_handler.optional_field_callback(
        fake_update(callback_data="description_skip"), context
    )
    assert context.user_data["step"] == "summary"
    assert context.user_data["new_task"]["assignee"] is None
    html = context.bot._post.await_args.kwargs["data"]["rich_message"]["html"]
    assert "assign_confirm_create" in html
    assert "assign_change_create" not in html


@pytest.mark.asyncio
async def test_disabled_priority_callback_does_not_mutate_draft():
    context = FakeContext(profile(disabled_features={"priority"}))
    context.user_data = {
        "new_task": {"title": "Safe draft"},
        "step": "priority",
        "create_task_message_id": 501,
    }
    update = fake_update(callback_data="priority_high")
    await task_handler.priority_selected(update, context)
    assert "priority" not in context.user_data["new_task"]
    assert context.user_data["step"] == "priority"
    assert any(
        call.kwargs.get("show_alert") is True
        for call in update.callback_query.answer.await_args_list
    )


@pytest.mark.asyncio
async def test_rich_relative_deadline_uses_user_local_day(monkeypatch):
    monkeypatch.setattr(
        create_task_flow, "get_current_local_datetime_async",
        AsyncMock(return_value=("Asia/Baku", datetime(2026, 10, 11, 0, 30))),
    )
    monkeypatch.setattr(task_handler, "_category_options", AsyncMock(return_value=[]))
    context = FakeContext(profile())
    context.user_data = {
        "new_task": {"title": "Timezone test"},
        "step": "priority",
        "create_task_message_id": 501,
    }
    await task_handler.priority_selected(
        fake_update(callback_data="priority_medium"), context
    )
    html = context.bot._post.await_args.kwargs["data"]["rich_message"]["html"]
    assert "امروز" in html
    await task_handler.deadline_selected(
        fake_update(callback_data="deadline_1"), context
    )
    assert context.user_data["new_task"]["deadline"] == "2026-10-12"
    assert context.user_data["step"] == "category"


@pytest.mark.asyncio
async def test_rich_confirmation_retries_without_duplicate_task(
    test_db, monkeypatch,
):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    from services import task_media
    monkeypatch.setattr(task_media, "save_task_media_async", AsyncMock())

    request_id = str(uuid.uuid4())
    context = FakeContext(profile())
    context.user_data = {
        "new_task": {
            "title": "Retry-safe task", "priority": "medium",
            "_create_request_id": request_id,
        },
        "create_task_message_id": 501,
        "unrelated_state": "keep",
    }
    failed_once = False

    async def send_with_one_failure(method, data=None):
        nonlocal failed_once
        if method == "editMessageText" and not failed_once:
            failed_once = True
            raise RuntimeError("network disconnected after database commit")
        return {"message_id": 501}

    context.bot._post.side_effect = send_with_one_failure

    await task_handler.assignment_callback(
        fake_update(callback_data="assign_confirm_create"), context
    )
    assert context.user_data["new_task"]["_create_request_id"] == request_id

    await task_handler.assignment_callback(
        fake_update(callback_data="assign_confirm_create"), context
    )
    created = await fetch_all("tasks", "id=?", (request_id,))
    assert len(created) == 1
    assert created[0]["title"] == "Retry-safe task"
    assert context.user_data == {"unrelated_state": "keep"}


@pytest.mark.asyncio
async def test_database_reuses_creation_uuid_and_rejects_other_owner(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    request_id = str(uuid.uuid4())
    args = (42, "One task", "medium", "", "", "")
    first = await task_service.create_task_async(*args, creation_request_id=request_id)
    again = await task_service.create_task_async(*args, creation_request_id=request_id)
    assert first == again == request_id
    assert len(await fetch_all("tasks", "id=?", (request_id,))) == 1

    with pytest.raises(ValueError, match="creation_request_conflict"):
        await task_service.create_task_async(
            99, "Other", "medium", "", "", "",
            creation_request_id=request_id,
        )


@pytest.mark.asyncio
async def test_rich_handler_is_wrapped_when_registered():
    async def priority_rich(update, context):
        raise AssertionError("handler must not run without tasks.create")

    handler = SimpleNamespace(callback=priority_rich)
    app = SimpleNamespace(handlers={0: [handler]}, bot_data={})
    install_task_capabilities(app)
    update = fake_update(callback_data="priority_high")
    context = FakeContext(profile(denied_permissions={"tasks.create"}))
    await handler.callback(update, context)
    update.callback_query.answer.assert_awaited_once()
    assert update.callback_query.answer.await_args.kwargs["show_alert"] is True


def test_main_uses_canonical_rich_deadline_callback():
    import main
    assert main.deadline_selected is task_handler.deadline_selected
