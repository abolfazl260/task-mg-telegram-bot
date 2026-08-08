"""Lightweight guard for external synchronization jobs.

Prevents overlapping syncs per bot, skips unnecessary runs inside a minimum
interval, and executes blocking provider APIs outside the asyncio event loop.
"""

import asyncio
import logging
import threading
import time

from bot_context import set_current_bot_key
from services.integration_service import sync_all
from services.jira_service import sync_all_connections

logger = logging.getLogger(__name__)

_JIRA_MIN_INTERVAL = 300
_EXTERNAL_MIN_INTERVAL = 300
_LOCK = threading.Lock()
_RUNNING = set()
_LAST_RUN = {}


def _claim(bot_key: str, kind: str, min_interval: int) -> bool:
    key = (kind, bot_key)
    now = time.monotonic()
    with _LOCK:
        if key in _RUNNING:
            return False
        last = _LAST_RUN.get(key, 0.0)
        if now - last < min_interval:
            return False
        _RUNNING.add(key)
        _LAST_RUN[key] = now
        return True


def _release(bot_key: str, kind: str) -> None:
    with _LOCK:
        _RUNNING.discard((kind, bot_key))


def _run_sync(kind: str, bot_key: str):
    set_current_bot_key(bot_key)
    try:
        if kind == "jira":
            return sync_all_connections(bot_key)
        return sync_all(bot_key)
    finally:
        _release(bot_key, kind)


async def run_jira_sync(bot_key: str):
    if not _claim(bot_key, "jira", _JIRA_MIN_INTERVAL):
        return None
    try:
        return await asyncio.to_thread(_run_sync, "jira", bot_key)
    except Exception:
        _release(bot_key, "jira")
        raise


async def run_external_sync(bot_key: str):
    if not _claim(bot_key, "external", _EXTERNAL_MIN_INTERVAL):
        return None
    try:
        return await asyncio.to_thread(_run_sync, "external", bot_key)
    except Exception:
        _release(bot_key, "external")
        raise
