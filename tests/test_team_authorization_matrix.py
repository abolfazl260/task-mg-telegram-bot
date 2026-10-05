import pytest

from services import task_service, team_service


OWNER = 100
EDITOR = 200
VIEWER = 300
NON_MEMBER = 400


async def _team_with_roles():
    team = await team_service.acreate_team(OWNER, "Authorization Team")
    editor_ok, _, _ = await team_service.ajoin_team_by_code(
        EDITOR, team["editor_code"]
    )
    viewer_ok, _, _ = await team_service.ajoin_team_by_code(
        VIEWER, team["viewer_code"]
    )
    assert editor_ok is True
    assert viewer_ok is True

    task_id = await task_service.create_task_async(
        OWNER,
        "Protected team task",
        "medium",
        "",
        "Authorization Team",
        "",
        team_id=team["team_id"],
    )
    return team, task_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "can_view"),
    [
        (OWNER, True),
        (EDITOR, True),
        (VIEWER, True),
        (NON_MEMBER, False),
    ],
)
async def test_team_task_view_permission_matrix(test_db, user_id, can_view):
    team, task_id = await _team_with_roles()

    tasks = await task_service.get_team_tasks_async(
        team["team_id"], user_id, active_only=False
    )
    task_ids = {task["id"] for task in tasks}

    assert (task_id in task_ids) is can_view


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "can_write"),
    [
        (OWNER, True),
        (EDITOR, True),
        (VIEWER, False),
        (NON_MEMBER, False),
    ],
)
async def test_team_task_edit_permission_matrix(test_db, user_id, can_write):
    _, task_id = await _team_with_roles()

    reloaded_task = await task_service.get_task_by_id_async(task_id)
    assert reloaded_task is not None
    assert await task_service.user_can_modify_task_async(
        user_id, reloaded_task
    ) is can_write

    changed = await task_service.update_task_async(
        task_id, user_id, description=f"edited-by-{user_id}"
    )
    assert changed is can_write

    persisted = await task_service.get_task_by_id_async(task_id)
    if can_write:
        assert persisted["description"] == f"edited-by-{user_id}"
    else:
        assert persisted["description"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "can_write"),
    [
        (OWNER, True),
        (EDITOR, True),
        (VIEWER, False),
        (NON_MEMBER, False),
    ],
)
async def test_team_task_status_permission_matrix(test_db, user_id, can_write):
    _, task_id = await _team_with_roles()

    changed = await task_service.change_task_status_async(
        task_id, "in_progress", user_id
    )
    assert changed is can_write

    persisted = await task_service.get_task_by_id_async(task_id)
    assert persisted["status"] == ("in_progress" if can_write else "pending")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "can_write"),
    [
        (OWNER, True),
        (EDITOR, True),
        (VIEWER, False),
        (NON_MEMBER, False),
    ],
)
async def test_team_task_assignment_permission_matrix(test_db, user_id, can_write):
    _, task_id = await _team_with_roles()
    assignee = {
        "user_id": "500",
        "display_name": "Assignee",
        "username": "assignee",
    }

    assigned = await task_service.assign_task_async(
        task_id, assignee, user_id, "assigned"
    )
    assert assigned is can_write

    persisted = await task_service.get_task_by_id_async(task_id)
    if can_write:
        assert persisted["assignee_id"] == "500"

        removed = await task_service.assign_task_async(
            task_id, None, user_id, "removed"
        )
        assert removed is True
        persisted = await task_service.get_task_by_id_async(task_id)
        assert persisted["assignee_id"] is None
    else:
        assert persisted["assignee_id"] is None

        removed = await task_service.assign_task_async(
            task_id, None, user_id, "removed"
        )
        assert removed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "can_admin"),
    [
        (OWNER, True),
        (EDITOR, False),
        (VIEWER, False),
        (NON_MEMBER, False),
    ],
)
async def test_team_admin_permission_matrix(test_db, monkeypatch, user_id, can_admin):
    team, _ = await _team_with_roles()

    codes = iter(["ADMIN1", "ADMIN2"])

    async def fixed_code(length=6):
        return next(codes)

    monkeypatch.setattr(team_service, "_gen_code", fixed_code)

    ok, _, updated = await team_service.aregenerate_codes(
        user_id, team["team_id"]
    )

    assert ok is can_admin
    if can_admin:
        assert updated["editor_code"] == "ADMIN1"
        assert updated["viewer_code"] == "ADMIN2"
    else:
        assert updated is None


@pytest.mark.asyncio
async def test_permissions_survive_database_reload_and_block_viewer_writes(test_db):
    team, task_id = await _team_with_roles()

    reloaded_team = await team_service.aget_team(team["team_id"])
    reloaded_task = await task_service.get_task_by_id_async(task_id)

    assert reloaded_team["team_id"] == team["team_id"]
    assert reloaded_task["team_id"] == team["team_id"]
    assert await team_service.aget_member_role(
        team["team_id"], OWNER
    ) == team_service.ROLE_OWNER
    assert await team_service.aget_member_role(
        team["team_id"], EDITOR
    ) == team_service.ROLE_EDITOR
    assert await team_service.aget_member_role(
        team["team_id"], VIEWER
    ) == team_service.ROLE_VIEWER
    assert await team_service.aget_member_role(
        team["team_id"], NON_MEMBER
    ) is None

    assert await task_service.user_can_modify_task_async(OWNER, reloaded_task)
    assert await task_service.user_can_modify_task_async(EDITOR, reloaded_task)
    assert not await task_service.user_can_modify_task_async(VIEWER, reloaded_task)
    assert not await task_service.user_can_modify_task_async(
        NON_MEMBER, reloaded_task
    )

    assert await task_service.update_task_async(
        task_id, VIEWER, title="viewer bypass"
    ) is False
    assert await task_service.change_task_status_async(
        task_id, "done", VIEWER
    ) is False
    assert await task_service.assign_task_async(
        task_id,
        {"user_id": "500", "display_name": "Unauthorized"},
        VIEWER,
    ) is False

    final_task = await task_service.get_task_by_id_async(task_id)
    assert final_task["title"] == "Protected team task"
    assert final_task["status"] == "pending"
    assert final_task["assignee_id"] is None
