"""Back Office: accurate creator/assignee counts and bounded user task drill-down.

All fixtures use synthetic IDs. Clinic/workspace tasks are intentionally
excluded from this generic administrator's task explorer.
"""

from pathlib import Path

import pytest

from services import clinic_typed
from webapp.admin_api import (
    dashboard_stats,
    get_user_profile,
    list_user_tasks,
    list_users,
)


async def _seed(db):
    for uid in ("1", "2", "3", "4", "5"):
        await db.conn.execute(
            "INSERT INTO users(user_id,full_name,username,first_seen,last_seen) "
            "VALUES(?,?,?,?,?)",
            (uid, f"User {uid}", f"user{uid}", "2026-09-01", f"2026-10-0{uid}"),
        )
    tasks = (
        ("A-1", "default", "1", "2"),
        ("A-2", "default", "1", "1"),
        ("A-3", "default", "2", "3"),
        ("B-1", "other", "3", "2"),
        ("B-2", "other", "4", None),
    )
    for tid, bot, creator, assignee in tasks:
        await db.conn.execute(
            "INSERT INTO tasks(id,bot_key,user_id,title,assignee_id,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (tid, bot, creator, f"Task {tid}", assignee, "2026-10-01T12:00:00Z"),
        )
    await db.conn.commit()


@pytest.mark.asyncio
async def test_user_counts_distinguish_created_vs_assigned_across_bots(test_db):
    await _seed(test_db)

    all_users = await list_users()
    assert all_users["total"] == 5
    by_id = {item["user_id"]: item for item in all_users["users"]}
    assert (by_id["1"]["task_count"], by_id["1"]["assigned_task_count"]) == (2, 1)
    assert (by_id["2"]["task_count"], by_id["2"]["assigned_task_count"]) == (1, 2)
    assert (by_id["3"]["task_count"], by_id["3"]["assigned_task_count"]) == (1, 1)
    assert (by_id["5"]["task_count"], by_id["5"]["assigned_task_count"]) == (0, 0)

    default = await list_users(bot_key="default")
    assert default["total"] == 3
    scoped = {item["user_id"]: item for item in default["users"]}
    assert set(scoped) == {"1", "2", "3"}
    assert (scoped["1"]["task_count"], scoped["1"]["assigned_task_count"]) == (2, 1)
    assert (scoped["2"]["task_count"], scoped["2"]["assigned_task_count"]) == (1, 1)
    assert (scoped["3"]["task_count"], scoped["3"]["assigned_task_count"]) == (0, 1)

    other = await list_users(bot_key="other")
    assert other["total"] == 3
    other_by_id = {item["user_id"]: item for item in other["users"]}
    assert set(other_by_id) == {"2", "3", "4"}
    assert (other_by_id["2"]["task_count"], other_by_id["2"]["assigned_task_count"]) == (0, 1)
    assert (other_by_id["3"]["task_count"], other_by_id["3"]["assigned_task_count"]) == (1, 0)


@pytest.mark.asyncio
async def test_bot_and_search_placeholders_are_bound_in_correct_sql_order(test_db):
    await _seed(test_db)
    cases = [
        ("default", "User 1", ["1"]),
        ("default", "user3", ["3"]),
        ("other", "User 2", ["2"]),
        ("other", "4", ["4"]),
    ]
    for bot, search, expected in cases:
        page = await list_users(bot_key=bot, search=search)
        assert [u["user_id"] for u in page["users"]] == expected
        profile = await get_user_profile(expected[0], bot_key=bot)
        assert profile is not None
        assert profile["user_id"] == expected[0]
        assert profile["task_count"] == page["users"][0]["task_count"]
        assert profile["assigned_task_count"] == page["users"][0]["assigned_task_count"]

    assert await get_user_profile("5", bot_key="default") is None
    assert await get_user_profile("2", bot_key="other") is not None
    assert (await list_users(search="invalid"))["total"] == 0


@pytest.mark.asyncio
async def test_user_task_list_is_paginated_and_aligned_with_per_user_counts(test_db):
    await _seed(test_db)
    for index in range(37):
        await test_db.conn.execute(
            "INSERT INTO tasks(id,bot_key,user_id,title,assignee_id,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (f"MORE-{index:02d}", "default", "1", f"Item {index}", "2",
             f"2026-10-02T12:{index:02d}:00Z"),
        )
    await test_db.conn.commit()
    creator = await get_user_profile("1", "default")
    assigned = await get_user_profile("2", "default")
    assert creator["task_count"] == 39
    assert assigned["assigned_task_count"] == 38

    p1 = await list_user_tasks("1", "default", view="created", limit=25, offset=0)
    p2 = await list_user_tasks("1", "default", view="created", limit=25, offset=25)
    assert p1["total"] == p2["total"] == 39
    assert len(p1["tasks"]) == 25
    assert len(p2["tasks"]) == 14
    assert len({t["id"] for t in p1["tasks"] + p2["tasks"]}) == 39
    assert set(t["bot_key"] for t in p1["tasks"] + p2["tasks"]) == {"default"}
    assert all(t["user_id"] == "1" for t in p1["tasks"] + p2["tasks"])

    assigned_page = await list_user_tasks("2", "default", view="assigned", limit=100)
    assert assigned_page["total"] == 38
    assert len(assigned_page["tasks"]) == 38
    assert all(t["assignee_id"] == "2" for t in assigned_page["tasks"])

    self_assigned = await list_user_tasks("1", "default", view="assigned")
    assert self_assigned["total"] == 1
    assert self_assigned["tasks"][0]["id"] == "A-2"
    assert (await list_user_tasks("2", "other", view="assigned"))["total"] == 1
    assert (await list_user_tasks("2", "default", view="created"))["total"] == 1
    assert (await list_user_tasks("2", "other", view="created"))["total"] == 0
    assert len((await list_user_tasks("1", "default", limit=1000))["tasks"]) <= 100
    assert (await list_user_tasks("1", "default", offset=-100))["offset"] == 0
    with pytest.raises(ValueError, match="invalid_user_task_view"):
        await list_user_tasks("1", view="all")


@pytest.mark.asyncio
async def test_recent_users_dashboard_contains_matching_per_user_counts(test_db):
    await _seed(test_db)
    dashboard = await dashboard_stats("default")
    recent = {u["user_id"]: u for u in dashboard["latest_users"]}
    assert "1" in recent
    assert recent["1"]["task_count"] == 2
    assert recent["1"]["assigned_task_count"] == 1
    assert recent["3"]["task_count"] == 0
    assert recent["3"]["assigned_task_count"] == 1
    assert dashboard["tasks"]["total"] == 3


@pytest.mark.asyncio
async def test_clinic_patient_items_are_excluded_from_admin_task_lists(clinic):
    patient = await clinic_typed.create_patient_async(
        clinic["owner"], clinic["a"], "Protected patient"
    )
    creator = patient["user_id"]
    created = await list_user_tasks(creator, "clinic")
    assert created["total"] == 0 and created["tasks"] == []
    assert await get_user_profile(creator, "clinic") is None
    assert (await list_users(bot_key="clinic"))["total"] == 0
    all_users = await list_users()
    assert any(u["user_id"] == creator for u in all_users["users"])


def test_admin_user_counts_and_detail_pagination_are_rendered_in_ui():
    root = Path(__file__).resolve().parents[1]
    js = (root / "webapp/static/admin/admin.js").read_text(encoding="utf-8")
    html = (root / "webapp/static/admin/index.html").read_text(encoding="utf-8")
    server = (root / "webapp/server.py").read_text(encoding="utf-8")
    assert "<span>Created</span><span>Assigned</span>" in js
    assert "u.assigned_task_count??0" in js
    assert 'view:userTaskView' not in js  # Uses explicit bound request arguments.
    assert "async function loadUserTasks()" in js
    assert "new URLSearchParams({view,limit:String(userTaskLimit),offset:String(offset)})" in js
    assert 'id="createdTaskTab"' in html
    assert 'id="assignedTaskTab"' in html
    assert 'id="prevUserTasks"' in html and 'id="nextUserTasks"' in html
    assert 'view not in {"created","assigned"}' in server
