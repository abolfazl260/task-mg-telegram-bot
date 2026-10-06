from __future__ import annotations

import asyncio

import pytest

from services import sync_scheduler


@pytest.fixture(autouse=True)
def reset_scheduler_state(monkeypatch):
    with sync_scheduler._LOCK:
        sync_scheduler._RUNNING.clear()
        sync_scheduler._LAST_SUCCESS.clear()
    monkeypatch.setattr(sync_scheduler, "set_current_bot_key", lambda _key: None)
    yield
    with sync_scheduler._LOCK:
        sync_scheduler._RUNNING.clear()
        sync_scheduler._LAST_SUCCESS.clear()


async def _immediate_to_thread(func, *args):
    return func(*args)


@pytest.mark.asyncio
async def test_same_bot_and_sync_kind_cannot_overlap(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def controlled_to_thread(func, *args):
        kind, bot_key = args
        if (kind, bot_key) == ("jira", "alpha"):
            started.set()
            await release.wait()
        return func(*args)

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", controlled_to_thread)
    monkeypatch.setattr(
        sync_scheduler,
        "sync_all_connections",
        lambda bot_key: {"success": True, "bot_key": bot_key},
    )

    first = asyncio.create_task(sync_scheduler.run_jira_sync("alpha"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert await sync_scheduler.run_jira_sync("alpha") is None
    assert ("jira", "alpha") in sync_scheduler._RUNNING

    release.set()
    assert await asyncio.wait_for(first, timeout=1) == {
        "success": True,
        "bot_key": "alpha",
    }
    assert ("jira", "alpha") not in sync_scheduler._RUNNING


@pytest.mark.asyncio
async def test_different_bots_run_independently(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def controlled_to_thread(func, *args):
        kind, bot_key = args
        if (kind, bot_key) == ("jira", "alpha"):
            started.set()
            await release.wait()
        return func(*args)

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", controlled_to_thread)
    monkeypatch.setattr(
        sync_scheduler,
        "sync_all_connections",
        lambda bot_key: {"success": True, "bot_key": bot_key},
    )

    alpha = asyncio.create_task(sync_scheduler.run_jira_sync("alpha"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert await sync_scheduler.run_jira_sync("beta") == {
        "success": True,
        "bot_key": "beta",
    }
    assert ("jira", "alpha") in sync_scheduler._RUNNING
    assert ("jira", "beta") not in sync_scheduler._RUNNING

    release.set()
    await asyncio.wait_for(alpha, timeout=1)


@pytest.mark.asyncio
async def test_jira_and_external_sync_do_not_block_each_other(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def controlled_to_thread(func, *args):
        kind, bot_key = args
        if (kind, bot_key) == ("jira", "alpha"):
            started.set()
            await release.wait()
        return func(*args)

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", controlled_to_thread)
    monkeypatch.setattr(
        sync_scheduler,
        "sync_all_connections",
        lambda _bot_key: {"success": True},
    )
    monkeypatch.setattr(sync_scheduler, "sync_all", lambda _bot_key: [])

    jira = asyncio.create_task(sync_scheduler.run_jira_sync("alpha"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert await sync_scheduler.run_external_sync("alpha") == []
    assert ("jira", "alpha") in sync_scheduler._RUNNING
    assert ("external", "alpha") not in sync_scheduler._RUNNING

    release.set()
    await asyncio.wait_for(jira, timeout=1)


@pytest.mark.asyncio
async def test_minimum_interval_skips_unnecessary_reruns(monkeypatch):
    clock = {"now": 1_000.0}
    calls = {"count": 0}

    def jira_sync(_bot_key):
        calls["count"] += 1
        return {"success": True}

    monkeypatch.setattr(sync_scheduler.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", _immediate_to_thread)
    monkeypatch.setattr(sync_scheduler, "sync_all_connections", jira_sync)

    assert await sync_scheduler.run_jira_sync("alpha") == {"success": True}
    assert calls["count"] == 1

    assert await sync_scheduler.run_jira_sync("alpha") is None
    assert calls["count"] == 1

    clock["now"] += sync_scheduler._JIRA_MIN_INTERVAL - 1
    assert await sync_scheduler.run_jira_sync("alpha") is None
    assert calls["count"] == 1

    clock["now"] += 1
    assert await sync_scheduler.run_jira_sync("alpha") == {"success": True}
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_success_updates_last_success_and_releases_lock(monkeypatch):
    clock = {"now": 321.5}

    monkeypatch.setattr(sync_scheduler.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", _immediate_to_thread)
    monkeypatch.setattr(
        sync_scheduler,
        "sync_all_connections",
        lambda _bot_key: {"success": True},
    )

    await sync_scheduler.run_jira_sync("alpha")

    assert sync_scheduler._LAST_SUCCESS[("jira", "alpha")] == 321.5
    assert ("jira", "alpha") not in sync_scheduler._RUNNING


@pytest.mark.asyncio
async def test_failed_or_partial_jira_sync_is_not_marked_successful(monkeypatch):
    calls = {"count": 0}

    def jira_sync(_bot_key):
        calls["count"] += 1
        return {
            "success": False,
            "partial": True,
            "failed_connections": 1,
        }

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", _immediate_to_thread)
    monkeypatch.setattr(sync_scheduler, "sync_all_connections", jira_sync)

    result = await sync_scheduler.run_jira_sync("alpha")
    assert result["success"] is False
    assert ("jira", "alpha") not in sync_scheduler._LAST_SUCCESS
    assert ("jira", "alpha") not in sync_scheduler._RUNNING

    await sync_scheduler.run_jira_sync("alpha")
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_external_provider_error_is_not_marked_successful(monkeypatch):
    calls = {"count": 0}
    failed_result = [
        (
            "42",
            [
                ("google_tasks", 0, "provider_error"),
            ],
        )
    ]

    def external_sync(_bot_key):
        calls["count"] += 1
        return failed_result

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", _immediate_to_thread)
    monkeypatch.setattr(sync_scheduler, "sync_all", external_sync)

    assert await sync_scheduler.run_external_sync("alpha") == failed_result
    assert ("external", "alpha") not in sync_scheduler._LAST_SUCCESS
    assert ("external", "alpha") not in sync_scheduler._RUNNING

    await sync_scheduler.run_external_sync("alpha")
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_exception_releases_running_lock_and_allows_retry(monkeypatch):
    calls = {"count": 0}

    def failing_sync(_bot_key):
        calls["count"] += 1
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(sync_scheduler.asyncio, "to_thread", _immediate_to_thread)
    monkeypatch.setattr(sync_scheduler, "sync_all_connections", failing_sync)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await sync_scheduler.run_jira_sync("alpha")

    assert ("jira", "alpha") not in sync_scheduler._RUNNING
    assert ("jira", "alpha") not in sync_scheduler._LAST_SUCCESS

    monkeypatch.setattr(
        sync_scheduler,
        "sync_all_connections",
        lambda _bot_key: {"success": True},
    )
    assert await sync_scheduler.run_jira_sync("alpha") == {"success": True}
    assert calls["count"] == 1
