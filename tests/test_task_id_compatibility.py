import uuid

import pytest

from handlers.task import _is_bare_task_id
from services import task_service
from services.integration_service import _task_marker
from utils.keyboard import task_action_keyboard


def _assert_uuid4(value: str) -> None:
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert str(parsed) == value


@pytest.mark.asyncio
async def test_create_task_uses_full_uuid4_and_supports_lookup_update(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    task_id = await task_service.create_task_async(
        100, "UUID task", "medium", "", "dev", "uuid"
    )

    _assert_uuid4(task_id)
    assert len(task_id) == 36

    task = await task_service.get_task_by_id_async(task_id)
    assert task["id"] == task_id

    assert await task_service.update_task_async(task_id, 100, title="Updated UUID task")
    assert (await task_service.get_task_by_id_async(task_id))["title"] == "Updated UUID task"


@pytest.mark.asyncio
async def test_save_task_without_explicit_id_uses_full_uuid4(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")

    task_id = await task_service.save_task_async(
        ["", "100", "Saved task", "medium", "pending", "", "", "", "", "", "", "", "", "", ""]
    )

    _assert_uuid4(task_id)
    assert len(task_id) == 36


@pytest.mark.asyncio
async def test_legacy_eight_character_task_id_remains_supported(test_db, monkeypatch):
    monkeypatch.setattr(task_service, "_bot", lambda: "test")
    legacy_id = "a1b2c3d4"

    saved_id = await task_service.save_task_async(
        [legacy_id, "100", "Legacy task", "medium", "pending", "", "", "", "", "", "", "", "", "", ""]
    )

    assert saved_id == legacy_id
    assert (await task_service.get_task_by_id_async(legacy_id))["title"] == "Legacy task"
    assert await task_service.update_task_async(legacy_id, 100, title="Updated legacy task")
    assert (await task_service.get_task_by_id_async(legacy_id))["title"] == "Updated legacy task"


def test_task_id_text_detection_accepts_legacy_and_full_uuid():
    new_id = str(uuid.uuid4())

    assert _is_bare_task_id("a1b2c3d4")
    assert _is_bare_task_id(new_id)
    assert not _is_bare_task_id("not-a-task-id")
    assert not _is_bare_task_id("123456789")


def test_task_action_callbacks_fit_telegram_limit_with_full_uuid():
    task_id = str(uuid.uuid4())
    keyboard = task_action_keyboard(task_id, "pending")

    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]

    assert callbacks
    assert all(task_id in callback for callback in callbacks)
    assert all(len(callback.encode("utf-8")) <= 64 for callback in callbacks)


def test_external_integration_marker_preserves_full_uuid():
    task_id = str(uuid.uuid4())

    assert _task_marker(task_id) == f"[BOT_TASK:{task_id}]"
