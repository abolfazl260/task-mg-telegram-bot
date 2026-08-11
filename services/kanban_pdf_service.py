from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
TERMINAL_OR_INACTIVE = {
    "done", "completed", "complete", "closed", "close", "cancelled", "canceled",
    "rejected", "reject", "archived", "archive", "inactive", "disabled", "draft",
    "preparation", "preparing", "ready", "blocked", "finished",
}


def _normalise_status(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_active_status(value: object) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    key = _normalise_status(raw)
    if key in TERMINAL_OR_INACTIVE:
        return False
    if any(token in key for token in ("inactive", "disabled", "archived", "preparation", "preparing")):
        return False
    if any(token in raw for token in ("غیرفعال", "بسته", "آماده‌سازی", "آماده سازی", "لغو شده", "رد شده")):
        return False
    return True


def _status_label(status: str) -> str:
    return {
        "pending": "شروع‌نشده",
        "in_progress": "در حال انجام",
        "done": "انجام‌شده",
        "cancelled": "لغو شده",
    }.get(status, status)


def _short_title(title: object, limit: int = 52) -> str:
    text = " ".join(str(title or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text or "بدون عنوان"
    return text[: max(1, limit - 1)].rstrip() + "…"


def _font_path() -> Path:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("فونت یونیکد مناسب برای تولید PDF پیدا نشد.")


def _register_font() -> str:
    name = "KanbanUnicode"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(_font_path())))
    return name


def _rtl_text(text: str) -> str:
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _text_fit(c: canvas.Canvas, text: str, width: float, font_name: str, start_size: float = 10.0) -> tuple[str, float]:
    size = start_size
    rendered = _rtl_text(text)
    while size > 7.0 and pdfmetrics.stringWidth(rendered, font_name, size) > width:
        size -= 0.5
    return rendered, size


def active_statuses(tasks: Iterable[dict]) -> list[str]:
    statuses: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status and status not in seen and is_active_status(status):
            seen.add(status)
            statuses.append(status)
    return statuses


def build_kanban_pdf(tasks: list[dict]) -> BytesIO:
    statuses = active_statuses(tasks)
    if not statuses:
        raise ValueError("هیچ وضعیت فعال و واقعی برای ساخت کانبان برد وجود ندارد.")

    page_size = landscape(A4 if len(statuses) <= 4 else A3)
    page_width, page_height = page_size
    margin = 12 * mm
    gap = 5 * mm
    header_h = 13 * mm
    box_h = 14 * mm
    box_gap = 3 * mm
    usable_width = page_width - 2 * margin - gap * (len(statuses) - 1)
    col_w = usable_width / len(statuses)
    max_rows = max(1, int((page_height - 2 * margin - header_h) // (box_h + box_gap)))
    font_name = _register_font()

    columns: dict[str, list[dict]] = {status: [] for status in statuses}
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status in columns:
            columns[status].append(task)

    for items in columns.values():
        items.sort(key=lambda t: (PRIORITY_ORDER.get(str(t.get("priority") or "").lower(), 3), str(t.get("created_at") or ""), str(t.get("id") or "")))

    total_pages = max(1, max((len(items) + max_rows - 1) // max_rows for items in columns.values()))
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=page_size)
    c.setTitle("کانبان برد")
    c.setAuthor("Task Manager Bot")

    for page in range(total_pages):
        for index, status in enumerate(statuses):
            x = margin + index * (col_w + gap)
            header_y = page_height - margin - header_h
            c.roundRect(x, header_y, col_w, header_h, 4 * mm, stroke=1, fill=0)
            label, label_size = _text_fit(c, _status_label(status), col_w - 8 * mm, font_name, 10)
            c.setFont(font_name, label_size)
            c.drawCentredString(x + col_w / 2, header_y + header_h / 2 - label_size * 0.35, label)

            items = columns[status][page * max_rows : (page + 1) * max_rows]
            for row, task in enumerate(items):
                y = header_y - box_gap - (row + 1) * box_h - row * box_gap
                c.roundRect(x, y, col_w, box_h, 3 * mm, stroke=1, fill=0)
                title, size = _text_fit(c, _short_title(task.get("title")), col_w - 8 * mm, font_name, 9.5)
                c.setFont(font_name, size)
                c.drawCentredString(x + col_w / 2, y + box_h / 2 - size * 0.35, title)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer
