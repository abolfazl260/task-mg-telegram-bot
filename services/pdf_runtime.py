"""Shared runtime controls for CPU-heavy PDF rendering."""

from __future__ import annotations

import asyncio
from io import BytesIO
from types import ModuleType

PDF_RENDER_SEMAPHORE = asyncio.Semaphore(2)
PDF_RENDER_TIMEOUT_SECONDS = 120
_pdf_fonts_warmed = False
_BACKGROUND_RENDER_TASKS: set[asyncio.Task] = set()


def warm_pdf_fonts() -> None:
    """Register PDF fonts once during application/module startup."""
    global _pdf_fonts_warmed
    if _pdf_fonts_warmed:
        return
    from services import kanban_pdf_service, calendar_pdf_service
    _freeze_font_registration(kanban_pdf_service, "KanbanUnicode")
    _freeze_font_registration(calendar_pdf_service, "CalendarUnicode")
    _pdf_fonts_warmed = True


def _freeze_font_registration(module: ModuleType, expected_name: str) -> None:
    current = getattr(module, "_register_font", None)
    if current is None:
        return
    font_name = current()
    if font_name != expected_name:
        raise RuntimeError(f"Unexpected PDF font registration name: {font_name}")

    def cached_font_name() -> str:
        return font_name

    module._register_font = cached_font_name
    module._PDF_FONT_NAME = font_name


async def _render_guarded(renderer, args: tuple) -> object:
    async with PDF_RENDER_SEMAPHORE:
        return await asyncio.to_thread(renderer, *args)


def _discard_render_task(task: asyncio.Task) -> None:
    _BACKGROUND_RENDER_TASKS.discard(task)
    if task.cancelled():
        return
    try:
        result = task.result()
    except Exception:
        return
    if isinstance(result, BytesIO):
        result.close()


async def render_pdf_in_worker(renderer, *args):
    """Run synchronous PDF rendering off-loop with bounded concurrency.

    A timeout only stops waiting for the worker; Python cannot forcibly stop a
    running thread. The shielded task therefore keeps its semaphore slot until
    the actual renderer finishes, preventing timed-out jobs from multiplying
    CPU pressure. A completed timed-out BytesIO is closed automatically.
    """
    task = asyncio.create_task(_render_guarded(renderer, args))
    _BACKGROUND_RENDER_TASKS.add(task)
    try:
        return await asyncio.wait_for(
            asyncio.shield(task),
            timeout=PDF_RENDER_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        task.add_done_callback(_discard_render_task)
        raise
    except asyncio.CancelledError:
        task.add_done_callback(_discard_render_task)
        raise
    finally:
        if task.done():
            _discard_render_task(task)
