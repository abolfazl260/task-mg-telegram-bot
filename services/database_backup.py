from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from telegram.error import NetworkError, RetryAfter, TelegramError

from config import ADMIN_IDS
from services import database

logger = logging.getLogger(__name__)

BACKUP_INTERVAL_SECONDS = 24 * 60 * 60
BACKUP_FIRST_RUN_SECONDS = 5 * 60
MAX_PART_BYTES = 20_000_000
SEND_RETRY_ATTEMPTS = 3
SEND_RETRY_BASE_SECONDS = 2.0
MIN_START_GAP_SECONDS = 23 * 60 * 60

_backup_running = False
_last_backup_started_at = 0.0


@dataclass(frozen=True)
class BackupPackage:
    created_at: datetime
    snapshot_size: int
    archive_size: int
    parts: tuple[Path, ...]


def _authorized_admin_ids() -> tuple[int, ...]:
    return tuple(
        int(value)
        for value in ADMIN_IDS
        if str(value).strip().isdigit()
    )


def _safe_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        logger.warning(
            "database_backup chmod_failed file=%s mode=%s",
            path.name,
            oct(mode),
        )


def _create_sqlite_snapshot(source_path: Path, snapshot_path: Path) -> int:
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError("Configured database file does not exist")

    source = sqlite3.connect(
        f"file:{source_path.as_posix()}?mode=ro",
        uri=True,
        timeout=database.SQLITE_TIMEOUT_SECONDS,
    )
    destination = sqlite3.connect(str(snapshot_path))
    try:
        source.backup(destination)
        checks = destination.execute("PRAGMA quick_check").fetchall()
        if not checks or any(str(row[0]).lower() != "ok" for row in checks):
            raise RuntimeError("SQLite backup integrity check failed")
        destination.commit()
    finally:
        destination.close()
        source.close()

    _safe_chmod(snapshot_path, 0o600)
    size = snapshot_path.stat().st_size
    if size <= 0:
        raise RuntimeError("SQLite backup snapshot is empty")
    return size


def _verify_archive(path: Path, max_part_bytes: int) -> None:
    if not path.exists() or not path.is_file() or not os.access(path, os.R_OK):
        raise RuntimeError(f"Backup archive is not readable: {path.name}")
    size = path.stat().st_size
    if size <= 0:
        raise RuntimeError(f"Backup archive is empty: {path.name}")
    if size > max_part_bytes:
        raise RuntimeError(
            f"Backup archive exceeds configured part limit: {path.name}"
        )
    with zipfile.ZipFile(path, "r") as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"Backup archive integrity check failed: {path.name}")
        if not archive.namelist():
            raise RuntimeError(f"Backup archive has no content: {path.name}")


def _write_zip(source_path: Path, archive_path: Path, arcname: str) -> None:
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        archive.write(source_path, arcname=arcname)
    _safe_chmod(archive_path, 0o600)


def _multipart_chunk_size(max_part_bytes: int) -> int:
    margin = max(1_024, max_part_bytes // 20)
    return max(1, max_part_bytes - margin)


def _prepare_backup_parts(
    source_path: Path,
    work_dir: Path,
    *,
    max_part_bytes: int = MAX_PART_BYTES,
    created_at: datetime | None = None,
) -> BackupPackage:
    if max_part_bytes <= 0:
        raise ValueError("max_part_bytes must be positive")

    created_at = created_at or datetime.now(timezone.utc)
    stamp = created_at.strftime("%Y-%m-%d-%H%M%S")
    base_name = f"database-backup-{stamp}"
    snapshot_path = work_dir / f"{base_name}.db"
    snapshot_size = _create_sqlite_snapshot(source_path, snapshot_path)

    single_archive = work_dir / f"{base_name}-part-01.zip"
    _write_zip(snapshot_path, single_archive, snapshot_path.name)
    if single_archive.stat().st_size <= max_part_bytes:
        _verify_archive(single_archive, max_part_bytes)
        return BackupPackage(
            created_at=created_at,
            snapshot_size=snapshot_size,
            archive_size=single_archive.stat().st_size,
            parts=(single_archive,),
        )

    single_archive.unlink()
    chunk_size = _multipart_chunk_size(max_part_bytes)
    parts: list[Path] = []
    with snapshot_path.open("rb") as source:
        index = 1
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            raw_part = work_dir / f".{base_name}-part-{index:02d}.dbpart"
            raw_part.write_bytes(chunk)
            _safe_chmod(raw_part, 0o600)
            archive_path = work_dir / f"{base_name}-part-{index:02d}.zip"
            try:
                _write_zip(
                    raw_part,
                    archive_path,
                    f"{base_name}-part-{index:02d}.dbpart",
                )
            finally:
                raw_part.unlink(missing_ok=True)
            _verify_archive(archive_path, max_part_bytes)
            parts.append(archive_path)
            index += 1

    if not parts:
        raise RuntimeError("No backup archive parts were generated")

    return BackupPackage(
        created_at=created_at,
        snapshot_size=snapshot_size,
        archive_size=sum(part.stat().st_size for part in parts),
        parts=tuple(parts),
    )


def _retry_after_seconds(exc: RetryAfter, attempt: int) -> float:
    value = exc.retry_after
    if hasattr(value, "total_seconds"):
        return max(float(value.total_seconds()), SEND_RETRY_BASE_SECONDS)
    try:
        return max(float(value), SEND_RETRY_BASE_SECONDS)
    except (TypeError, ValueError):
        return SEND_RETRY_BASE_SECONDS * attempt


async def _send_part_with_retry(
    bot,
    *,
    admin_id: int,
    part_path: Path,
    caption: str,
    part_index: int,
) -> None:
    last_error: BaseException | None = None
    for attempt in range(1, SEND_RETRY_ATTEMPTS + 1):
        try:
            with part_path.open("rb") as document:
                await bot.send_document(
                    chat_id=admin_id,
                    document=document,
                    filename=part_path.name,
                    caption=caption,
                )
            return
        except RetryAfter as exc:
            last_error = exc
            delay = _retry_after_seconds(exc, attempt)
            error_type = type(exc).__name__
        except NetworkError as exc:
            last_error = exc
            delay = SEND_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            error_type = type(exc).__name__
        except TelegramError as exc:
            logger.error(
                "database_backup send_failed admin_id=%s part=%s attempt=%s "
                "error_type=%s",
                admin_id,
                part_index,
                attempt,
                type(exc).__name__,
            )
            raise

        logger.warning(
            "database_backup send_retry admin_id=%s part=%s attempt=%s "
            "error_type=%s",
            admin_id,
            part_index,
            attempt,
            error_type,
        )
        if attempt >= SEND_RETRY_ATTEMPTS:
            raise RuntimeError(
                f"Backup delivery failed for part {part_index}"
            ) from last_error
        await asyncio.sleep(delay)


async def _send_status_best_effort(bot, admin_ids: tuple[int, ...], text: str) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except TelegramError:
            logger.warning(
                "database_backup status_message_failed admin_id=%s",
                admin_id,
            )


def _format_size(size: int) -> str:
    return f"{size / (1024 * 1024):.2f} MB"


async def run_database_backup(
    bot,
    *,
    source_path: Path | str | None = None,
    admin_ids: tuple[int, ...] | None = None,
    max_part_bytes: int = MAX_PART_BYTES,
    temp_parent: Path | str | None = None,
) -> BackupPackage:
    configured_source = database.DB_PATH if source_path is None else source_path
    if str(configured_source) == ":memory:":
        raise RuntimeError("In-memory databases cannot be exported by this backup job")
    source = Path(configured_source).expanduser().resolve()
    authorized_admins = _authorized_admin_ids() if admin_ids is None else admin_ids
    if not authorized_admins:
        raise RuntimeError("No authorized admin Telegram IDs are configured")

    parent = None if temp_parent is None else str(Path(temp_parent))
    temp_dir = Path(tempfile.mkdtemp(prefix="taskmg-db-backup-", dir=parent))
    _safe_chmod(temp_dir, 0o700)
    package: BackupPackage | None = None
    primary_error: BaseException | None = None

    logger.info(
        "database_backup start admin_count=%s",
        len(authorized_admins),
    )
    try:
        package = await asyncio.to_thread(
            _prepare_backup_parts,
            source,
            temp_dir,
            max_part_bytes=max_part_bytes,
        )
        logger.info(
            "database_backup prepared parts=%s snapshot_bytes=%s archive_bytes=%s "
            "part_bytes=%s",
            len(package.parts),
            package.snapshot_size,
            package.archive_size,
            ",".join(str(part.stat().st_size) for part in package.parts),
        )

        total_parts = len(package.parts)
        timestamp = package.created_at.isoformat()
        for admin_id in authorized_admins:
            for index, part_path in enumerate(package.parts, start=1):
                caption = (
                    "TaskMG database backup\n"
                    f"Timestamp: {timestamp}\n"
                    f"Part: {index}/{total_parts}\n"
                    f"Total archive size: {_format_size(package.archive_size)}\n"
                    f"Snapshot size: {_format_size(package.snapshot_size)}\n"
                    "Status: delivery in progress"
                )
                try:
                    await _send_part_with_retry(
                        bot,
                        admin_id=admin_id,
                        part_path=part_path,
                        caption=caption,
                        part_index=index,
                    )
                except Exception:
                    logger.exception(
                        "database_backup delivery_failed admin_id=%s part=%s/%s",
                        admin_id,
                        index,
                        total_parts,
                    )
                    raise

        await _send_status_best_effort(
            bot,
            authorized_admins,
            (
                "✅ TaskMG database backup completed\n"
                f"Timestamp: {timestamp}\n"
                f"Parts: {total_parts}\n"
                f"Total archive size: {_format_size(package.archive_size)}"
            ),
        )
        logger.info(
            "database_backup complete parts=%s archive_bytes=%s",
            total_parts,
            package.archive_size,
        )
        return package
    except Exception as exc:
        primary_error = exc
        logger.exception("database_backup failed error_type=%s", type(exc).__name__)
        await _send_status_best_effort(
            bot,
            authorized_admins,
            "❌ TaskMG database backup failed. Check server logs for details.",
        )
        raise
    finally:
        try:
            shutil.rmtree(temp_dir)
            logger.info("database_backup cleanup_complete")
        except OSError:
            logger.exception("database_backup cleanup_failed")
            if primary_error is None:
                raise


async def _claim_backup_due() -> bool:
    """Persist the backup throttle as one atomic Core transaction.

    This avoids blocking the Telegram event loop on sqlite3 BEGIN IMMEDIATE
    and ensures a single claim wins across independent bot processes.
    """
    async def claim(conn):
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS backup_state "
            "(name TEXT PRIMARY KEY, started_at REAL NOT NULL)"
        )
        async with conn.execute(
            "SELECT started_at FROM backup_state WHERE name='database'"
        ) as cur:
            row = await cur.fetchone()
        wall_now = time.time()
        if row and wall_now - float(row[0]) < MIN_START_GAP_SECONDS:
            return False
        await conn.execute(
            "INSERT INTO backup_state(name,started_at) VALUES('database',?) "
            "ON CONFLICT(name) DO UPDATE SET started_at=excluded.started_at",
            (wall_now,),
        )
        return True

    return await database.atomic_write("backup_claim", claim)


async def database_backup_job(context) -> None:
    global _backup_running, _last_backup_started_at

    now = time.monotonic()
    if _backup_running:
        logger.warning("database_backup skipped reason=already_running")
        return
    if _last_backup_started_at and now - _last_backup_started_at < MIN_START_GAP_SECONDS:
        logger.info("database_backup skipped reason=recent_run")
        return

    try:
        if not await _claim_backup_due():
            logger.info("database_backup skipped reason=persisted_recent_run")
            return
    except sqlite3.OperationalError:
        # The shared DB service already logged attempts and correlation ID.
        logger.error("database_backup skipped reason=sqlite_lock_exhausted")
        return

    _backup_running = True
    _last_backup_started_at = now
    try:
        await run_database_backup(context.bot)
    except Exception:
        logger.exception("database_backup scheduled_run_failed")
    finally:
        _backup_running = False
