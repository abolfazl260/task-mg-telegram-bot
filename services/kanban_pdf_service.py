from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "بالا": 0, "متوسط": 1, "پایین": 2}
TERMINAL_OR_INACTIVE = {
    "done", "completed", "complete", "closed", "close", "cancelled", "canceled",
    "rejected", "reject", "archived", "archive", "inactive", "disabled", "draft",
    "preparation", "preparing", "finished",
}

# A restrained modern palette. Statuses keep their identity, while cards remain neutral.
STATUS_STYLES = {
    "pending": ("شروع‌نشده", "#64748B"),
    "in_progress": ("در حال انجام", "#2563EB"),
}
DEFAULT_STATUS_COLOR = "#475569"
PRIORITY_MARKERS = {
    "high": "●",
    "medium": "●",
    "low": "●",
    "بالا": "●",
    "متوسط": "●",
    "پایین": "●",
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
    if key in {"انجام‌شده", "انجام شده", "تکمیل‌شده", "تکمیل شده", "بسته", "لغو شده", "رد شده", "آماده‌سازی", "آماده سازی"}:
        return False
    if any(token in key for token in ("inactive", "disabled", "archived", "preparation", "preparing")):
        return False
    if any(token in raw for token in ("غیرفعال", "آماده‌سازی", "آماده سازی")):
        return False
    return True


def _status_label(status: str) -> str:
    return {
        "pending": "شروع‌نشده",
        "in_progress": "در حال انجام",
        "done": "انجام‌شده",
        "cancelled": "لغو شده",
    }.get(status, status)


def _status_style(status: str) -> tuple[str, str]:
    return STATUS_STYLES.get(status, (_status_label(status), DEFAULT_STATUS_COLOR))


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


def _clean(value: object, fallback: str = "") -> str:
    return " ".join(str(value or fallback).replace("\n", " ").split()).strip()


def _short_text(value: object, limit: int) -> str:
    text = _clean(value)
    if not text:
        return ""
    return text if len(text) <= limit else text[: max(1, limit - 1)].rstrip() + "…"


def _text_fit(c: canvas.Canvas, text: str, width: float, font_name: str, start_size: float = 8.0, min_size: float = 6.0) -> tuple[str, float]:
    size = start_size
    rendered = _rtl_text(text)
    while size > min_size and pdfmetrics.stringWidth(rendered, font_name, size) > width:
        size -= 0.25
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


def _priority_label(value: object) -> str:
    key = _normalise_status(value)
    return {"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(key, _clean(value, "بدون اولویت"))


def _task_assignee(task: dict) -> str:
    for key in ("assignee_name", "assigned_to_name", "owner_name", "assignee", "owner"):
        value = _clean(task.get(key))
        if value:
            return value
    return "بدون مسئول"


def _task_category(task: dict) -> str:
    return _clean(task.get("category"), "بدون دسته‌بندی") or "بدون دسته‌بندی"


def _task_deadline(task: dict) -> str:
    return _clean(task.get("deadline"), "بدون موعد") or "بدون موعد"


def _task_tags(task: dict) -> str:
    tags = task.get("tags")
    if isinstance(tags, (list, tuple, set)):
        text = "، ".join(_clean(item) for item in tags if _clean(item))
    else:
        text = _clean(tags)
    return _short_text(text, 30) if text else "بدون تگ"


def _draw_rtl(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float, align: str = "right") -> None:
    rendered = _rtl_text(text)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _draw_card(c: canvas.Canvas, task: dict, x: float, y: float, w: float, h: float, font: str) -> None:
    # White card with a very light border and a slim priority indicator.
    c.setFillColor(HexColor("#FFFFFF"))
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=1)

    priority = _normalise_status(task.get("priority"))
    marker = PRIORITY_MARKERS.get(priority, "●")
    marker_color = {"high": "#DC2626", "medium": "#D97706", "low": "#16A34A", "بالا": "#DC2626", "متوسط": "#D97706", "پایین": "#16A34A"}.get(priority, "#94A3B8")
    c.setFillColor(HexColor(marker_color))
    c.roundRect(x, y, 1.8 * mm, h, 1 * mm, stroke=0, fill=1)

    pad = 4 * mm
    right = x + w - pad
    top = y + h - pad

    title = _short_text(task.get("title"), 52)
    _draw_rtl(c, title or "بدون عنوان", right, top - 1, font, 8.4)

    meta_y = top - 6.2 * mm
    c.setFillColor(HexColor("#475569"))
    _draw_rtl(c, f"اولویت: {_priority_label(task.get('priority'))}", right, meta_y, font, 6.4)
    _draw_rtl(c, f"موعد: {_task_deadline(task)}", right, meta_y - 4.4 * mm, font, 6.4)

    # Two compact secondary parameters. These are intentionally shown on every card
    # so the board remains useful without opening the task.
    left = x + pad
    bottom = y + pad
    _draw_rtl(c, f"مسئول: {_short_text(_task_assignee(task), 24)}", right, bottom + 1.0 * mm, font, 5.9)
    _draw_rtl(c, f"دسته: {_short_text(_task_category(task), 24)}", right, bottom + 5.0 * mm, font, 5.9)

    tags = _task_tags(task)
    if tags != "بدون تگ":
        _draw_rtl(c, f"تگ: {tags}", left + 0.5 * mm, bottom + 1.0 * mm, font, 5.6, align="left")


def build_kanban_pdf(tasks: list[dict]) -> BytesIO:
    statuses = active_statuses(tasks)
    if not statuses:
        raise ValueError("هیچ وضعیت فعال و واقعی برای ساخت کانبان برد وجود ندارد.")

    # A3 landscape gives enough horizontal room for status columns while keeping
    # the whole board on exactly one page.
    page_width, page_height = landscape(A3)
    margin_x = 10 * mm
    margin_top = 9 * mm
    margin_bottom = 8 * mm
    gap = 4 * mm
    title_h = 15 * mm
    header_h = 12 * mm
    card_gap = 2.5 * mm

    usable_width = page_width - 2 * margin_x
    col_w = (usable_width - gap * (len(statuses) - 1)) / len(statuses)
    font = _register_font()

    columns: dict[str, list[dict]] = {status: [] for status in statuses}
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status in columns:
            columns[status].append(task)
    for items in columns.values():
        items.sort(key=lambda t: (
            PRIORITY_ORDER.get(_normalise_status(t.get("priority")), 3),
            str(t.get("deadline") or ""),
            str(t.get("created_at") or ""),
            str(t.get("id") or ""),
        ))

    # Calculate one compact card height so every column fits on the same page.
    available_h = page_height - margin_top - margin_bottom - title_h - header_h - 6 * mm
    max_count = max((len(items) for items in columns.values()), default=1)
    card_h = max(14 * mm, min(25 * mm, (available_h - max(0, max_count - 1) * card_gap) / max_count))

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    c.setTitle("کانبان برد")
    c.setAuthor("Task Manager Bot")

    # Header
    c.setFillColor(HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    c.setFillColor(HexColor("#0F172A"))
    _draw_rtl(c, "کانبان برد وظایف", page_width - margin_x, page_height - margin_top - 5 * mm, font, 14)
    active_count = sum(len(items) for items in columns.values())
    c.setFillColor(HexColor("#64748B"))
    _draw_rtl(c, f"{active_count} وظیفه فعال  •  {len(statuses)} وضعیت", page_width - margin_x, page_height - margin_top - 11 * mm, font, 6.8)

    board_top = page_height - margin_top - title_h
    for index, status in enumerate(statuses):
        x = margin_x + index * (col_w + gap)
        label, accent = _status_style(status)
        header_y = board_top - header_h

        # Column container
        c.setFillColor(HexColor("#F1F5F9"))
        c.setStrokeColor(HexColor("#E2E8F0"))
        c.roundRect(x, margin_bottom, col_w, board_top - margin_bottom, 3 * mm, stroke=1, fill=1)

        # Colored column header
        c.setFillColor(HexColor(accent))
        c.roundRect(x, header_y, col_w, header_h, 3 * mm, stroke=0, fill=1)
        c.rect(x, header_y, col_w, 3 * mm, stroke=0, fill=1)
        c.setFillColor(white)
        _draw_rtl(c, f"{label}  •  {len(columns[status])}", x + col_w - 4 * mm, header_y + 4.0 * mm, font, 8.2)

        items = columns[status]
        for row, task in enumerate(items):
            y = header_y - 2.5 * mm - card_h - row * (card_h + card_gap)
            _draw_card(c, task, x + 2.5 * mm, y, col_w - 5 * mm, card_h, font)

    # Footer: intentionally small and unobtrusive.
    c.setFillColor(HexColor("#94A3B8"))
    _draw_rtl(c, "برد کانبان • نمای یک‌صفحه‌ای", margin_x, 3.5 * mm, font, 5.5, align="left")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
