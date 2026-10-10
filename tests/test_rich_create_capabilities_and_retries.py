"""Regressions for task-creation permissions, dates and retry safety."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from handlers import create_task_flow as rich
from handlers import create_task_rich_progress as progress
from services import task_service
from services.database import fetch_all_sql


def profile(*, disabled_features=(), disabled_permissions=(), disabled_options=()):
    disabled_features = set(disabled_features)
    disabled_permissions = set(disabled_permissions)
    disabled_options = set(disabled_options)
    return SimpleNamespace(
        feature_enabled=lambda key: key not in disabled_features,
        permission_enabled=lambda key: key not in disabled_permissions,
        settings={"task_options": {key: False for key in disabled_options}},
    )


def context(*, disabled_features=(), disabled_permissions=(), disabled_options=()):
    return SimpleNamespace(
        bot_data={"bot_config": profile(
            disabled_features=disabled_features,
            disabled_permissions=disabled_permissions,
            disabled_options=disabled_options,
        )},
        user_data={"new_task": {"title": "Prepare report", "priority": "medium"}},
    )


@pytest.mark.asyncio
async def test_hidden_category_and_tags_advance_to_description(monkeypatch):
    ctx = context(disabled_features={"categories", "tags"})
    edits = AsyncMock()
    monkeypatch.setattr(rich, "_edit_rich", edits)
    module = SimpleNamespace(_category_options=AsyncMock(side_effect=AssertionError("not expected")))
    await rich._show_category(module, SimpleNamespace(), ctx, 41)
    assert ctx.user_data["step"] == "description"
    assert ctx.user_data["new_task"]["category"] == ""
    assert ctx.user_data["new_task"]["tags"] == ""
    assert "category_pick_" not in edits.await_args.args[2]


@pytest.mark.asyncio
async def test_disabled_assignment_skips_selector(monkeypatch):
    ctx = context(disabled_options={"allow_assignment"})
    summary = AsyncMock()
    monkeypatch.setattr(rich, "_show_summary", summary)
    await rich._show_assignment(SimpleNamespace(), ctx)
    assert ctx.user_data["new_task"]["assignee"] is None
    assert ctx.user_data["new_task"]["team_id"] == ""
    summary.assert_awaited_once()


def test_assignee_change_button_is_hidden_without_permission():
    ctx = context(disabled_permissions={"assignment.manage"})
    html = progress._summary_rich_html(ctx.user_data["new_task"], ctx)
    assert "assign_confirm_create" in html
    assert "assign_change_create" not in html


def test_local_day_is_used_for_deadline_labels():
    html = rich._deadline_html(date(2026, 10, 11))
    assert rich._deadline_label(0, date(2026, 10, 11)) in html
    assert "deadline_0" in html
    assert "تاریخ و زمان دلخواه" not in html


def test_create_state_cleanup_removes_retry_and_media_state_only():
    ctx = context()
    ctx.user_data.update({
        "create_task_request_id": "example-key",
        "description_media": [{"type": "photo", "file_id": "abc"}],
        "description_text_parts": ["old description"],
        "create_task_media_saved": True,
        "other_flow": "keep",
    })
    rich.clear_create_task_state(ctx)
    assert ctx.user_data == {"other_flow": "keep"}


@pytest.mark.asyncio
async def test_core_reuses_committed_task_for_same_request(test_db):
    user = 15091
    request_id = str(uuid.uuid4())
    first = await task_service.create_task_async(
        user, "Original", "medium", "", "", "", idempotency_key=request_id,
    )
    second = await task_service.create_task_async(
        user, "Changed retry title", "medium", "", "", "", idempotency_key=request_id,
    )
    assert first == second
    rows = await fetch_all_sql("SELECT id FROM tasks WHERE id=?", (first,))
    assert len(rows) == 1
    attempts = await fetch_all_sql(
        "SELECT * FROM task_creation_requests WHERE request_id=?", (request_id,)
    )
    assert len(attempts) == 1
    assert attempts[0]["task_id"] == first
    with pytest.raises(PermissionError):
        await task_service.create_task_async(
            user + 1, "Unauthorized retry", "medium", "", "", "",
            idempotency_key=request_id,
        )


@pytest.mark.asyncio
async def test_core_different_requests_create_distinct_tasks(test_db):
    user = 15092
    first = await task_service.create_task_async(
        user, "One", "medium", "", "", "", idempotency_key=str(uuid.uuid4())
    )
    second = await task_service.create_task_async(
        user, "Two", "medium", "", "", "", idempotency_key=str(uuid.uuid4())
    )
    assert first != second
