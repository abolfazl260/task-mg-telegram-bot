from services import integration_service


def _connection(user_id, provider):
    return {
        "user_id": str(user_id),
        "bot_key": "default",
        "provider": provider,
        "enabled": 1,
        "access_token": "token",
        "refresh_token": "refresh",
        "expires_at": "9999999999",
        "external_list_id": "list-1",
    }


def _stub_provider_io(monkeypatch, connections, created):
    monkeypatch.setattr(
        integration_service,
        "get_connection",
        lambda user_id, provider, bot_key="default": connections.get(
            (str(user_id), provider, bot_key)
        ),
    )
    monkeypatch.setattr(integration_service, "_refresh", lambda row: "token")
    monkeypatch.setattr(
        integration_service, "_microsoft_lists", lambda token: [{"id": "list-1"}]
    )
    monkeypatch.setattr(
        integration_service, "_google_lists", lambda token: [{"id": "list-1"}]
    )
    monkeypatch.setattr(
        integration_service, "_ensure_list", lambda row, lists: "list-1"
    )
    monkeypatch.setattr(integration_service, "_load_task_links", lambda *args: [])
    monkeypatch.setattr(integration_service, "_save_task_link", lambda *args: None)

    def request_json(url, token, method="GET", payload=None):
        if "graph.microsoft.com" in url:
            return {"value": []}
        return {"items": []}

    monkeypatch.setattr(integration_service, "_request_json", request_json)

    def create_external(row, task):
        created.append((row["provider"], task["id"]))
        return {"id": f"{row['provider']}-{task['id']}", "status": "pending"}

    monkeypatch.setattr(integration_service, "_create_external", create_external)
    monkeypatch.setattr(integration_service, "sync_execute", lambda *args, **kwargs: None)


def test_manual_sync_reads_only_users_tasks_once_for_both_providers(monkeypatch):
    user_id = "42"
    connections = {
        (user_id, "microsoft", "default"): _connection(user_id, "microsoft"),
        (user_id, "google", "default"): _connection(user_id, "google"),
    }
    created = []
    task_reads = []

    def db_sync_all(table, where="", params=()):
        assert table == "tasks"
        task_reads.append((where, params))
        if where != "user_id=?" or params != (user_id,):
            raise AssertionError("integration sync must use a user-scoped task query")
        return [
            {"id": "task-a", "user_id": user_id, "status": "pending"},
            {"id": "task-b", "user_id": user_id, "status": "pending"},
        ]

    monkeypatch.setattr(integration_service, "db_sync_all", db_sync_all)
    _stub_provider_io(monkeypatch, connections, created)

    results = integration_service.sync_user(user_id)

    assert task_reads == [("user_id=?", (user_id,))]
    assert created == [
        ("microsoft", "task-a"),
        ("microsoft", "task-b"),
        ("google", "task-a"),
        ("google", "task-b"),
    ]
    assert results == [
        ("microsoft", 2, None),
        ("google", 2, None),
    ]


def test_scheduled_sync_reads_one_scoped_task_set_per_connected_user(monkeypatch):
    users = ["100", "200", "300"]
    connections = {}
    integration_rows = []
    for user_id in users:
        for provider in ("microsoft", "google"):
            connections[(user_id, provider, "default")] = _connection(
                user_id, provider
            )
            integration_rows.append(
                {
                    "user_id": user_id,
                    "bot_key": "default",
                    "provider": provider,
                    "enabled": 1,
                }
            )

    created = []
    task_reads = []

    def db_sync_all(table, where="", params=()):
        if table == "external_connections":
            return integration_rows
        if table == "tasks":
            if where != "user_id=?" or len(params) != 1:
                raise AssertionError("global task scans are forbidden in integration sync")
            user_id = str(params[0])
            task_reads.append(user_id)
            return [{"id": f"task-{user_id}", "user_id": user_id, "status": "pending"}]
        raise AssertionError(f"unexpected table read: {table}")

    monkeypatch.setattr(integration_service, "db_sync_all", db_sync_all)
    _stub_provider_io(monkeypatch, connections, created)

    results = integration_service.sync_all()

    assert [user_id for user_id, _ in results] == users
    assert task_reads == users
    assert len(created) == len(users) * 2


def test_sync_user_respects_allowed_provider_list(monkeypatch):
    user_id = "42"
    connections = {
        (user_id, "microsoft", "default"): _connection(user_id, "microsoft"),
        (user_id, "google", "default"): _connection(user_id, "google"),
    }
    created = []

    monkeypatch.setattr(
        integration_service,
        "db_sync_all",
        lambda table, where="", params=(): [
            {"id": "task-a", "user_id": user_id, "status": "pending"}
        ] if table == "tasks" else [],
    )
    _stub_provider_io(monkeypatch, connections, created)

    results = integration_service.sync_user(user_id, providers=("microsoft",))

    assert created == [("microsoft", "task-a")]
    assert results == [("microsoft", 1, None)]
