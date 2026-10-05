from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import guest, reports, task
from services import csv_export, excel_service


@pytest.mark.asyncio
async def test_csv_export_uses_async_task_reader(monkeypatch):
    tasks = [
        {
            "id": "1",
            "title": "Async CSV",
            "priority": "high",
            "status": "pending",
            "deadline": "",
            "category": "work",
            "tags": "async",
            "description": "native",
            "created_at": "2026-10-05 10:00",
        }
    ]
    async_reader = AsyncMock(return_value=tasks)
    monkeypatch.setattr(csv_export, "get_active_tasks_async", async_reader)

    def fail_sync_reader(*args, **kwargs):
        raise AssertionError("sync task reader must not be used by async CSV export")

    monkeypatch.setattr(csv_export, "get_active_tasks", fail_sync_reader)

    buffer, count = await csv_export.build_csv_bytes_async(42)

    assert count == 1
    assert "Async CSV" in buffer.getvalue().decode("utf-8-sig")
    async_reader.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_excel_export_uses_async_task_reader(monkeypatch):
    tasks = [
        {
            "id": "1",
            "title": "Async Excel",
            "priority": "medium",
            "status": "pending",
            "deadline": "",
            "category": "work",
            "tags": "",
            "created_at": "2026-10-05 10:00",
        }
    ]
    async_reader = AsyncMock(return_value=tasks)
    monkeypatch.setattr(excel_service, "get_active_tasks_async", async_reader)

    def fail_sync_reader(*args, **kwargs):
        raise AssertionError("sync task reader must not be used by async Excel export")

    monkeypatch.setattr(excel_service, "get_active_tasks", fail_sync_reader)

    buffer, count = await excel_service.build_excel_bytes_async(42)

    assert count == 1
    assert buffer.getvalue().startswith(b"PK")
    async_reader.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_download_csv_handler_awaits_async_export(monkeypatch):
    query = SimpleNamespace(
        answer=AsyncMock(),
        message=SimpleNamespace(
            reply_text=AsyncMock(),
            reply_document=AsyncMock(),
        ),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42),
    )
    context = SimpleNamespace()
    exporter = AsyncMock(return_value=(SimpleNamespace(), 2))
    monkeypatch.setattr(task, "build_csv_bytes_async", exporter)

    await task.download_csv(update, context)

    exporter.assert_awaited_once_with(42)
    query.message.reply_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_reports_handler_awaits_async_task_reader(monkeypatch):
    query = SimpleNamespace(answer=AsyncMock(), message=SimpleNamespace(reply_text=AsyncMock()))
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=42),
        effective_chat=SimpleNamespace(id=777),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(_post=AsyncMock())
    )
    reader = AsyncMock(return_value=[])
    monkeypatch.setattr(reports, "get_all_user_tasks_async", reader)

    await reports.report_all_tasks(update, context)

    reader.assert_awaited_once_with(42)
    query.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_guest_report_awaits_async_task_reader(monkeypatch):
    reader = AsyncMock(return_value=[])
    monkeypatch.setattr(guest, "get_all_user_tasks_async", reader)

    text = await guest._build_guest_report(42)

    reader.assert_awaited_once_with(42)
    assert "هنوز هیچ تسکی" in text
