"""Shared runtime controls for CPU-heavy PDF rendering."""

from __future__ import annotations

import asyncio
from types import ModuleType

PDF_RENDER_SEMAPHORE = asyncio.Semaphore(2)
PDF_RENDER_TIMEOUT_SECONDS = 120
_pdf_fonts_warmed = False


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


async def render_pdf_in_worker(renderer, *args):
    """Run synchronous ReportLab/RTL work outside the asyncio event loop."""
    async with PDF_RENDER_SEMAPHORE:
        return await asyncio.wait_for(
            asyncio.to_thread(renderer, *args),
            timeout=PDF_RENDER_TIMEOUT_SECONDS,
        )
