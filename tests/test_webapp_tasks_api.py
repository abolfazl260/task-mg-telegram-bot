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

    async def fake_visible(user_id, team_id=None):
        return [{"id": "different"}]

    monkeypatch.setattr(tasks_api.task_service, "get_task_by_id_async", fake_get)
    monkeypatch.setattr(tasks_api.task_service, "get_all_user_tasks_async", fake_visible)

    with pytest.raises(tasks_api.WebAppTaskAccessError):
        await tasks_api.get_task(42, "secret-task")
