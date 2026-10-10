from __future__ import annotations

import pytest

from webapp import tasks_api


@pytest.mark.asyncio
async def test_list_tasks_sets_webapp_bot_context(monkeypatch):
    called = {}

    def fake_context():
        called["set"] = True
        return "clinic"

    async def fake_list(user_id, team_id):
        called["args"] = (user_id, team_id)
        return [{"id": "1"}]

    monkeypatch.setattr(tasks_api, "set_webapp_bot_context", fake_context)
    monkeypatch.setattr(tasks_api.task_service, "get_all_user_tasks_async", fake_list)

    result = await tasks_api.list_tasks(42, team_id="team-1")

    assert result == [{"id": "1"}]
    assert called == {"set": True, "args": (42, "team-1")}


@pytest.mark.asyncio
async def test_get_task_rejects_task_not_visible(monkeypatch):
    monkeypatch.setattr(tasks_api, "set_webapp_bot_context", lambda: "clinic")

    async def fake_get(task_id):
        return {"id": task_id}

    async def fake_visible(user_id, task_id):
        assert user_id == 42
        assert task_id == "secret-task"
        return None

    monkeypatch.setattr(tasks_api.task_service, "get_task_by_id_async", fake_get)
    monkeypatch.setattr(tasks_api.task_service, "get_visible_task_by_id_async", fake_visible)

    with pytest.raises(tasks_api.WebAppTaskAccessError):
        await tasks_api.get_task(42, "secret-task")


@pytest.mark.asyncio
async def test_list_tasks_forwards_work_item_type_filter(monkeypatch):
    called = {}

    monkeypatch.setattr(
        tasks_api,
        "set_webapp_bot_context",
        lambda bot_key: called.setdefault("bot_key", bot_key),
    )

    async def fake_list(user_id, team_id, work_item_type=None):
        called["args"] = (user_id, team_id, work_item_type)
        return [{"id": "patient-1", "work_item_type": work_item_type}]

    monkeypatch.setattr(tasks_api.task_service, "get_all_user_tasks_async", fake_list)

    result = await tasks_api.list_tasks(
        42,
        "clinic",
        team_id=None,
        work_item_type="patient",
    )

    assert result == [{"id": "patient-1", "work_item_type": "patient"}]
    assert called == {"bot_key": "clinic", "args": (42, None, "patient")}


@pytest.mark.asyncio
async def test_create_task_forwards_work_item_type(monkeypatch):
    called = {}

    monkeypatch.setattr(tasks_api, "set_webapp_bot_context", lambda bot_key: bot_key)

    async def fake_create(**kwargs):
        called.update(kwargs)
        return "new-id"

    monkeypatch.setattr(tasks_api.task_service, "create_task_async", fake_create)

    task_id = await tasks_api.create_task(
        77,
        "clinic",
        title="Patient record",
        work_item_type="patient",
    )

    assert task_id == "new-id"
    assert called["user_id"] == 77
    assert called["work_item_type"] == "patient"


@pytest.mark.asyncio
async def test_webapp_task_page_forwards_bounded_query_and_context(monkeypatch):
    called = {}
    monkeypatch.setattr(tasks_api, "set_webapp_bot_context", lambda key: called.setdefault("bot", key))

    async def page(user_id, team_id, **options):
        called.update(user_id=user_id, team_id=team_id, **options)
        return {"tasks": [{"id": "one"}], "total": 2, "limit": 1, "offset": 1, "has_more": False}

    monkeypatch.setattr(tasks_api.task_service, "list_visible_tasks_page_async", page)
    result = await tasks_api.list_tasks_page(
        42, "clinic", team_id="my-team", active_only=True,
        limit=1, offset=1, work_item_type="task",
    )
    assert result["total"] == 2
    assert called == {
        "bot": "clinic", "user_id": 42, "team_id": "my-team",
        "active": True, "work_item_type": "task", "limit": 1, "offset": 1,
    }


@pytest.mark.parametrize("query", [
    {"limit": ["0"]}, {"limit": ["101"]}, {"limit": ["abc"]},
    {"offset": ["-1"]}, {"offset": ["nope"]},
])
def test_task_page_request_rejects_invalid_limits(query):
    with pytest.raises(ValueError, match="invalid_pagination"):
        tasks_api.task_page_params(query)


def test_task_page_request_default_and_explicit_offsets():
    assert tasks_api.task_page_params({}) == (50, 0)
    assert tasks_api.task_page_params({"limit": ["25"], "offset": ["50"]}) == (25, 50)
