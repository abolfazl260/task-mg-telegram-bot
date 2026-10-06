import pytest

from webapp.database_explorer import database_explorer_rows, database_explorer_tables


async def _seed_users(test_db):
    await test_db.conn.executemany(
        """
        INSERT INTO users(user_id, full_name, username, first_seen, last_seen, messages_count)
        VALUES(?,?,?,?,?,?)
        """,
        [
            ("u1", "Alpha", "alpha", "2026-10-01T10:00:00Z", "2026-10-02T10:00:00Z", 2),
            ("u2", "Beta", "beta", "2026-10-02T10:00:00Z", "2026-10-04T10:00:00Z", 7),
            ("u3", "Gamma", "gamma", "2026-10-03T10:00:00Z", "2026-10-06T10:00:00Z", 12),
        ],
    )
    await test_db.conn.commit()


async def test_database_explorer_metadata_is_allowlisted_and_sensitive_fields_are_hidden(test_db):
    payload = await database_explorer_tables()
    tables = {table["name"]: table for table in payload["tables"]}

    assert payload["readonly"] is True
    assert {"users", "teams", "team_members", "tasks", "custom_bots"} <= set(tables)
    assert "patient_references" not in tables
    assert "clinic_cases" not in tables
    assert "external_connections" not in tables
    assert "jira_connections" not in tables

    team_columns = {column["name"] for column in tables["teams"]["columns"]}
    assert "editor_code" not in team_columns
    assert "viewer_code" not in team_columns

    bot_columns = {column["name"] for column in tables["custom_bots"]["columns"]}
    assert "bot_token" not in bot_columns

    task_columns = {column["name"] for column in tables["tasks"]["columns"]}
    assert "description" not in task_columns
    assert "patient_id" not in task_columns
    assert "case_id" not in task_columns


async def test_database_explorer_combines_filters_sorts_and_paginates_server_side(test_db):
    await _seed_users(test_db)

    filtered = await database_explorer_rows(
        "users",
        filters=[
            {"column": "full_name", "operator": "contains", "value": "a"},
            {"column": "messages_count", "operator": "greater_than", "value": "5"},
            {"column": "last_seen", "operator": "after", "value": "2026-10-03T00:00:00Z"},
        ],
        sort="messages_count",
        direction="desc",
        limit=50,
        offset=0,
    )
    assert filtered["total"] == 2
    assert [row["user_id"] for row in filtered["rows"]] == ["u3", "u2"]

    page = await database_explorer_rows(
        "users",
        sort="messages_count",
        direction="desc",
        limit=1,
        offset=1,
    )
    assert page["total"] == 3
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert [row["user_id"] for row in page["rows"]] == ["u2"]


async def test_database_explorer_core_tasks_do_not_leak_healthcare_scoped_rows(test_db):
    await test_db.conn.execute(
        "INSERT INTO users(user_id, full_name) VALUES(?,?)",
        ("u1", "Admin-visible user"),
    )
    await test_db.conn.execute(
        "INSERT INTO clinic_organizations(id, bot_key, name) VALUES(?,?,?)",
        ("org-1", "clinic", "Clinic"),
    )
    await test_db.conn.execute(
        "INSERT INTO clinic_branches(id, organization_id, name) VALUES(?,?,?)",
        ("branch-1", "org-1", "Main"),
    )
    await test_db.conn.execute(
        "INSERT INTO tasks(id, user_id, title, created_at) VALUES(?,?,?,?)",
        ("core-task", "u1", "Core task", "2026-10-01T00:00:00Z"),
    )
    await test_db.conn.execute(
        """
        INSERT INTO tasks(id, user_id, title, created_at, organization_id, branch_id)
        VALUES(?,?,?,?,?,?)
        """,
        ("clinic-task", "u1", "Clinic task", "2026-10-02T00:00:00Z", "org-1", "branch-1"),
    )
    await test_db.conn.commit()

    payload = await database_explorer_rows("tasks", sort="created_at", direction="desc")
    assert payload["total"] == 1
    assert [row["id"] for row in payload["rows"]] == ["core-task"]


async def test_database_explorer_rejects_unallowlisted_identifiers_and_invalid_filters(test_db):
    await _seed_users(test_db)

    with pytest.raises(ValueError, match="invalid_database_table"):
        await database_explorer_rows("users; DROP TABLE users")

    with pytest.raises(ValueError, match="invalid_sort_column"):
        await database_explorer_rows("users", sort="last_seen DESC, user_id")

    with pytest.raises(ValueError, match="invalid_filter_column"):
        await database_explorer_rows(
            "custom_bots",
            filters=[{"column": "bot_token", "operator": "contains", "value": "123"}],
        )

    with pytest.raises(ValueError, match="invalid_filter_operator"):
        await database_explorer_rows(
            "users",
            filters=[{"column": "messages_count", "operator": "contains", "value": "1"}],
        )

    with pytest.raises(ValueError, match="invalid_filter_range"):
        await database_explorer_rows(
            "users",
            filters=[
                {
                    "column": "messages_count",
                    "operator": "range",
                    "value": "10",
                    "value_to": "2",
                }
            ],
        )
