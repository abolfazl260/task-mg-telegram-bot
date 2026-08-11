"""Shared runtime controls for CPU-heavy PDF rendering."""

from __future__ import annotations

import asyncio

# A small per-process render gate prevents concurrent ReportLab/RTL workloads
# from exhausting CPU and memory when traffic spikes.
PDF_RENDER_SEMAPHORE = asyncio.Semaphore(2)
PDF_RENDER_TIMEOUT_SECONDS = 120


async def render_pdf_in_worker(renderer, *args):
    """Run a synchronous PDF renderer outside the asyncio event loop.

    The semaphore limits simultaneous renders in this process. Telegram I/O is
    intentionally not performed here; callers remain fully async.
    """
    async with PDF_RENDER_SEMAPHORE:
        return await asyncio.wait_for(
            asyncio.to_thread(renderer, *args),
            timeout=PDF_RENDER_TIMEOUT_SECONDS,
        )
