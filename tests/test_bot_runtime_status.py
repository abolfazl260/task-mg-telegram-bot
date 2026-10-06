from __future__ import annotations

import pytest
import pytest_asyncio

from services import database
from services.bot_runtime_status import get_runtime_status, record_runtime_status


@pytest_asyncio.fixture(autouse=True)
async def isolated_db(tmp_path, monkeypatch):
    database.shutdown_sync_loop()
    await database.close_all_dbs()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "runtime_status.db")
    await database.init_db()
    yield
    database.shutdown_sync_loop()
    await database.close_all_dbs()


@pytest.mark.asyncio
async def test_runtime_status_persists_error_and_lifecycle_timestamps():
    await record_runtime_status(
        "clinic",
        "error",
        desired_status="active",
        error="start_failed:RuntimeError",
    )
    failed = await get_runtime_status("clinic")
    assert failed["runtime_status"] == "error"
    assert failed["last_error"] == "start_failed:RuntimeError"
    assert failed["last_error_at"]

    await record_runtime_status(
        "clinic",
        "running",
        desired_status="active",
        event="started",
        clear_error=True,
    )
    running = await get_runtime_status("clinic")
    assert running["runtime_status"] == "running"
    assert running["desired_status"] == "active"
    assert running["last_started_at"]
    assert running["last_error"] == ""
    assert running["last_error_at"] == ""


@pytest.mark.asyncio
async def test_runtime_reload_timestamp_is_independent_from_start_timestamp():
    await record_runtime_status(
        "sales",
        "running",
        desired_status="active",
        event="started",
        clear_error=True,
    )
    started = await get_runtime_status("sales")

    await record_runtime_status(
        "sales",
        "running",
        desired_status="active",
        event="reloaded",
        clear_error=True,
    )
    reloaded = await get_runtime_status("sales")

    assert reloaded["last_started_at"] == started["last_started_at"]
    assert reloaded["last_reloaded_at"]
