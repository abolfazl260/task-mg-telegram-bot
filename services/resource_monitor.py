from __future__ import annotations

import asyncio
import logging
import os
import resource
import threading

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60
WARNING_RATIO = 0.70
CRITICAL_RATIO = 0.85


def open_fd_count() -> int | None:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except (FileNotFoundError, OSError):
        return None


def _soft_fd_limit() -> int | None:
    try:
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        return None if soft == resource.RLIM_INFINITY else int(soft)
    except (AttributeError, OSError, ValueError):
        return None


async def monitor_resources(stop_event: asyncio.Event) -> None:
    """Log process resource usage without creating long-lived resources."""
    soft_limit = _soft_fd_limit()
    while not stop_event.is_set():
        fd_count = open_fd_count()
        task_count = len(asyncio.all_tasks())
        thread_count = threading.active_count()
        if fd_count is not None and soft_limit:
            ratio = fd_count / soft_limit
            level = logging.INFO
            if ratio >= CRITICAL_RATIO:
                level = logging.ERROR
            elif ratio >= WARNING_RATIO:
                level = logging.WARNING
            logger.log(
                level,
                "RESOURCE_MONITOR pid=%s fd=%s/%s (%.1f%%) threads=%s asyncio_tasks=%s",
                os.getpid(), fd_count, soft_limit, ratio * 100, thread_count, task_count,
            )
        else:
            logger.info(
                "RESOURCE_MONITOR pid=%s fd=%s threads=%s asyncio_tasks=%s",
                os.getpid(), fd_count, thread_count, task_count,
            )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def start_resource_monitor(app) -> None:
    """Attach one monitor task to an Application instance."""
    if app.bot_data.get("resource_monitor_task") is not None:
        return
    stop_event = asyncio.Event()
    task = asyncio.create_task(monitor_resources(stop_event), name="resource-monitor")
    app.bot_data["resource_monitor_stop"] = stop_event
    app.bot_data["resource_monitor_task"] = task


async def stop_resource_monitor(app) -> None:
    stop_event = app.bot_data.pop("resource_monitor_stop", None)
    task = app.bot_data.pop("resource_monitor_task", None)
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        try:
            await task
        except asyncio.CancelledError:
            pass
