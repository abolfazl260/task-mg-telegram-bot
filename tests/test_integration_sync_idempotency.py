import pytest

from services import integration_service


def _install_sync_fakes(monkeypatch, provider, external_tasks=None):
    external_tasks = list(external_tasks or [])
    links = {}
    creates = []
    row = {
        "user_id": "42",
        "bot_key": "default",
        "provider": provider,
        "enabled": 1,
        "external_list_id": "list-1",
    }
    task = {
        "id": "task-1",
        "user_id": "42",
        "title": "Important task",
        "description": "Task body",
        "status": "pending",
        "deadline": "",
    }

    monkeypatch.setattr(integration_service, "get_connection", lambda *_: row)
    monkeypatch.setattr(integration_service, "_refresh", lambda _row: "token")
    monkeypatch.setattr(integration_service, "_read_user_tasks", lambda _user_id: [task.copy()])
    monkeypatch.setattr(integration_service, "sync_execute", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        integration_service,
        "_microsoft_lists",
        lambda _token: [{"id": "list-1", "displayName": "Tasks"}],
    )
    monkeypatch.setattr(
        integration_service,
        "_google_lists",
        lambda _token: [{"id": "list-1", "title": "Tasks"}],
    )
    monkeypatch.setattr(
        integration_service,
        "_load_task_links",
        lambda user_id, bot_key, name: [
            value
            for key, value in links.items()
            if key[:3] == (str(user_id), bot_key, name)
        ],
    )

    def save_link(user_id, bot_key, name, local_task_id, external_task_id, external_list_id):
        links[(str(user_id), bot_key, name, str(local_task_id))] = {
            "user_id": str(user_id),
            "bot_key": bot_key,
            "provider": name,
            "local_task_id": str(local_task_id),
            "external_task_id": str(external_task_id),
            "external_list_id": str(external_list_id),
        }

    monkeypatch.setattr(integration_service, "_save_task_link", save_link)

    def request_json(url, _token, method="GET", payload=None):
        if method == "POST":
            external_id = f"{provider}-external-{len(creates) + 1}"
            created = {"id": external_id, "status": "notStarted"}
            if provider == "microsoft":
                created["body"] = {"content": payload["body"]["content"]}
            else:
                created["notes"] = payload["notes"]
            external_tasks.append(created)
            creates.append(payload)
            return created
        if "tasks?" in url:
            return {"value": list(external_tasks)} if provider == "microsoft" else {"items": list(external_tasks)}
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(integration_service, "_request_json", request_json)
    return links, creates


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_repeated_sync_creates_external_task_only_once(monkeypatch, provider):
    links, creates = _install_sync_fakes(monkeypatch, provider)

    first = integration_service.sync_user("42", provider=provider)
    second = integration_service.sync_user("42", provider=provider)

    assert first == [(provider, 1, None)]
    assert second == [(provider, 0, None)]
    assert len(creates) == 1
    assert len(links) == 1
    payload = creates[0]
    notes = payload["body"]["content"] if provider == "microsoft" else payload["notes"]
    assert "[BOT_TASK:task-1]" in notes


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_legacy_marker_is_recovered_without_duplicate(monkeypatch, provider):
    marker = "[BOT_TASK:task-1]"
    existing = {"id": f"{provider}-legacy-1", "status": "notStarted"}
    if provider == "microsoft":
        existing["body"] = {"content": marker}
    else:
        existing["notes"] = marker

    links, creates = _install_sync_fakes(monkeypatch, provider, [existing])

    result = integration_service.sync_user("42", provider=provider)

    assert result == [(provider, 0, None)]
    assert creates == []
    assert len(links) == 1
    saved = next(iter(links.values()))
    assert saved["external_task_id"] == existing["id"]


def test_external_task_link_schema_enforces_scoped_uniqueness(db_schema):
    assert "CREATE TABLE IF NOT EXISTS external_task_links" in db_schema
    assert "UNIQUE(user_id,bot_key,provider,local_task_id)" in db_schema
    assert "UNIQUE(user_id,bot_key,provider,external_task_id)" in db_schema
