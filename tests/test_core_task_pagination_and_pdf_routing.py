"""Regression coverage for bounded Core reads and Telegram callback routing."""

from pathlib import Path

import pytest
from telegram.ext import CallbackQueryHandler

from bot_platform import BotProfile, DEFAULT_FEATURES
from services import task_service, team_service


@pytest.mark.asyncio
async def test_paged_visible_tasks_keep_scope_counts_and_stable_boundaries(test_db):
    team = await team_service.acreate_team("200", "Shared")
    other_team = await team_service.acreate_team("400", "Private")
    joined, _, _ = await team_service.ajoin_team_by_code("100", team["viewer_code"])
    assert joined is True
    for uid in ("100", "300"):
        await test_db.conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))

    rows = [
        (f"personal-{i:03d}", "default" if i % 2 else "other", "100", f"Task {i}",
         None, "pending" if i % 5 else "done", "2026-10-10", "medium")
        for i in range(65)
    ]
    rows += [
        ("shared", "other", "200", "Shared task", team["team_id"],
         "pending", "2026-10-10", "high"),
        ("foreign", "default", "300", "Foreign task", None,
         "pending", "2026-10-10", "high"),
        ("other-team", "default", "400", "Other team task", other_team["team_id"],
         "pending", "2026-10-10", "high"),
    ]
    await test_db.conn.executemany(
        """INSERT INTO tasks(id,bot_key,user_id,title,team_id,status,created_at,priority)
           VALUES(?,?,?,?,?,?,?,?)""", rows,
    )
    await test_db.conn.commit()

    pages = [
        await task_service.list_visible_tasks_page_async("100", limit=25, offset=offset)
        for offset in (0, 25, 50, 75)
    ]
    assert [p["total"] for p in pages] == [66] * 4
    assert [len(p["tasks"]) for p in pages] == [25, 25, 16, 0]
    assert [p["has_more"] for p in pages] == [True, True, False, False]
    ids = [item["id"] for page in pages for item in page["tasks"]]
    assert len(ids) == len(set(ids)) == 66
    assert "shared" in ids
    assert "foreign" not in ids and "other-team" not in ids
    assert ids == sorted(ids, reverse=True)

    active = await task_service.list_visible_tasks_page_async("100", active=True, limit=100)
    assert active["total"] == 53  # 52 pending personal tasks plus one team task.
    assert all(row["status"] == "pending" for row in active["tasks"])

    scoped = await task_service.list_visible_tasks_page_async(
        "100", team_id=team["team_id"], limit=10
    )
    assert scoped["total"] == 1 and scoped["tasks"][0]["id"] == "shared"
    denied = await task_service.list_visible_tasks_page_async(
        "300", team_id=team["team_id"]
    )
    assert denied["total"] == 0 and denied["tasks"] == []

    assert (await task_service.get_visible_task_by_id_async("100", "shared"))["id"] == "shared"
    assert await task_service.get_visible_task_by_id_async("100", "foreign") is None

    left, _ = await team_service.aleave_team("100", team["team_id"])
    assert left is True
    assert (await task_service.list_visible_tasks_page_async("100"))["total"] == 65
    assert await task_service.get_visible_task_by_id_async("100", "shared") is None


@pytest.mark.asyncio
async def test_paged_tasks_sorting_and_bounds(test_db):
    await test_db.conn.execute("INSERT INTO users(user_id) VALUES('100')")
    for ident, priority, deadline in (
        ("low", "low", ""),
        ("high", "high", "2026-10-12"),
        ("medium", "medium", "2026-10-11"),
    ):
        await test_db.conn.execute(
            "INSERT INTO tasks(id,bot_key,user_id,title,created_at,priority,deadline) VALUES(?,?,?,?,?,?,?)",
            (ident, "default", "100", ident, "2026-10-10", priority, deadline),
        )
    await test_db.conn.commit()
    by_priority = await task_service.list_visible_tasks_page_async("100", sort_key="priority")
    assert [row["id"] for row in by_priority["tasks"]] == ["high", "medium", "low"]
    by_deadline = await task_service.list_visible_tasks_page_async("100", sort_key="deadline")
    assert [row["id"] for row in by_deadline["tasks"]] == ["medium", "high", "low"]
    huge_page = await task_service.list_visible_tasks_page_async("100", limit=10000)
    assert huge_page["limit"] == 100
    with pytest.raises(ValueError, match="invalid_pagination"):
        await task_service.list_visible_tasks_page_async("100", limit=0)
    with pytest.raises(ValueError, match="invalid_pagination"):
        await task_service.list_visible_tasks_page_async("100", offset=-1)
    with pytest.raises(ValueError, match="invalid_task_sort"):
        await task_service.list_visible_tasks_page_async("100", sort_key="unsafe")


def test_calendar_pdf_callback_precedes_generic_report_handler():
    import main as main_module

    features = {key: False for key in DEFAULT_FEATURES}
    features.update({"core": True, "tasks": True, "reports": True})
    profile = BotProfile(
        key="routing-test", name="Routing test", username="routing_test_bot",
        token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", features=features,
    )
    app = main_module.build_application(profile)
    handlers = [
        handler for handler in app.handlers.get(0, [])
        if isinstance(handler, CallbackQueryHandler)
        and handler.pattern and handler.pattern.match("report_calendar_pdf")
    ]
    assert handlers
    assert handlers[0].callback is main_module.calendar_pdf_callback
    assert any(handler.callback is main_module.reports_callback for handler in handlers)


def test_bounded_web_task_list_has_visible_page_navigation():
    root = Path(__file__).resolve().parents[1]
    js = (root / "webapp/static/app.js").read_text(encoding="utf-8")
    html = (root / "webapp/static/index.html").read_text(encoding="utf-8")
    assert 'id="pagination"' in html
    assert "&limit=" in js and "&offset=" in js
    assert "renderTaskPagination()" in js
