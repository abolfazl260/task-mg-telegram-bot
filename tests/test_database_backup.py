from __future__ import annotations

import asyncio
import io
import os
import sqlite3
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import NetworkError

from services import database_backup


class FakeBot:
    def __init__(self, *, fail_documents: bool = False) -> None:
        self.fail_documents = fail_documents
        self.document_calls = 0
        self.documents = []
        self.messages = []

    async def send_document(
        self,
        *,
        chat_id,
        document,
        filename,
        caption,
    ):
        self.document_calls += 1
        payload = document.read()
        if self.fail_documents:
            raise NetworkError("temporary network failure")
        self.documents.append(
            {
                "chat_id": chat_id,
                "filename": filename,
                "caption": caption,
                "payload": payload,
            }
        )

    async def send_message(self, *, chat_id, text):
        self.messages.append({"chat_id": chat_id, "text": text})


def _create_database(path, payload_size: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE sample(id INTEGER PRIMARY KEY, payload BLOB NOT NULL)"
        )
        connection.execute(
            "INSERT INTO sample(payload) VALUES (?)",
            (os.urandom(payload_size),),
        )
        connection.commit()
    finally:
        connection.close()


def _assert_valid_zip(payload: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert names
        return names


async def test_single_part_backup_is_sent_and_temp_files_are_cleaned(tmp_path):
    source = tmp_path / "source.db"
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    _create_database(source, 2_000)
    bot = FakeBot()

    package = await database_backup.run_database_backup(
        bot,
        source_path=source,
        admin_ids=(101,),
        max_part_bytes=1_000_000,
        temp_parent=temp_root,
    )

    assert len(package.parts) == 1
    assert len(bot.documents) == 1
    sent = bot.documents[0]
    assert sent["chat_id"] == 101
    assert sent["filename"].startswith("database-backup-")
    assert sent["filename"].endswith("-part-01.zip")
    assert "Part: 1/1" in sent["caption"]
    assert len(sent["payload"]) <= 1_000_000
    assert _assert_valid_zip(sent["payload"])[0].endswith(".db")
    assert any("backup completed" in item["text"] for item in bot.messages)
    assert list(temp_root.iterdir()) == []
    assert source.exists()


async def test_large_backup_is_split_into_ordered_zip_parts(tmp_path):
    source = tmp_path / "source.db"
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    _create_database(source, 80_000)
    bot = FakeBot()
    limit = 12_000

    package = await database_backup.run_database_backup(
        bot,
        source_path=source,
        admin_ids=(202,),
        max_part_bytes=limit,
        temp_parent=temp_root,
    )

    assert len(package.parts) > 1
    assert len(bot.documents) == len(package.parts)
    filenames = [item["filename"] for item in bot.documents]
    assert filenames == sorted(filenames)
    for index, item in enumerate(bot.documents, start=1):
        assert item["chat_id"] == 202
        assert f"part-{index:02d}.zip" in item["filename"]
        assert len(item["payload"]) <= limit
        names = _assert_valid_zip(item["payload"])
        assert names == [
            item["filename"].replace(".zip", ".dbpart")
        ]
    assert list(temp_root.iterdir()) == []


async def test_send_failure_is_bounded_and_temp_files_are_cleaned(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.db"
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    _create_database(source, 2_000)
    bot = FakeBot(fail_documents=True)
    sleep = AsyncMock()
    monkeypatch.setattr(database_backup.asyncio, "sleep", sleep)

    with pytest.raises(RuntimeError, match="Backup delivery failed"):
        await database_backup.run_database_backup(
            bot,
            source_path=source,
            admin_ids=(303,),
            max_part_bytes=1_000_000,
            temp_parent=temp_root,
        )

    assert bot.document_calls == database_backup.SEND_RETRY_ATTEMPTS
    assert sleep.await_count == database_backup.SEND_RETRY_ATTEMPTS - 1
    assert any("backup failed" in item["text"] for item in bot.messages)
    assert list(temp_root.iterdir()) == []
    assert source.exists()


async def test_scheduled_job_prevents_overlapping_runs(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def fake_run(bot):
        calls.append(bot)
        started.set()
        await release.wait()

    monkeypatch.setattr(database_backup, "run_database_backup", fake_run)
    monkeypatch.setattr(database_backup, "_backup_running", False)
    monkeypatch.setattr(database_backup, "_last_backup_started_at", 0.0)

    context = SimpleNamespace(bot=object())
    first = asyncio.create_task(database_backup.database_backup_job(context))
    await started.wait()

    await database_backup.database_backup_job(context)

    assert calls == [context.bot]
    release.set()
    await first
