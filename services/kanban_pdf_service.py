from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "بالا": 0, "متوسط": 1, "پایین": 2}
PRIORITY_LABELS = {"high": "بالا", "medium": "متوسط", "low": "پایین"}
PRIORITY_COLORS = {"high": "#DC2626", "medium": "#D97706", "low": "#16A34A", "بالا": "#DC2626", "متوسط": "#D97706", "پایین": "#16A34A"}
STATUS_LABELS = {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده"}
STATUS_COLORS = ["#64748B", "#2563EB", "#16A34A", "#7C3AED", "#0891B2", "#C2410C"]
TERMINAL_OR_INACTIVE = {"done", "completed", "complete", "closed", "close", "cancelled", "canceled", "rejected", "reject", "archived", "archive", "inactive", "disabled", "draft", "preparation", "preparing", "finished"}


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
    return STATUS_LABELS.get(status, status or "بدون وضعیت")


def _font_path() -> Path:
    candidates = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"), Path("/Library/Fonts/Arial Unicode.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")]
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("فونت یونیکد مناسب برای تولید PDF پیدا نشد.")


def _register_font() -> str:
    name = "KanbanUnicode"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(_font_path())))
    return name


def _rtl(text: object) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(value))
    except Exception:
        return value


def _clean(value: object, fallback: str = "") -> str:
    return " ".join(str(value or fallback).replace("\n", " ").split()).strip()


def _short(value: object, limit: int) -> str:
    text = _clean(value)
    return text if len(text) <= limit else text[:max(1, limit - 1)].rstrip() + "…"


def _priority_label(value: object) -> str:
    key = _normalise_status(value)
    return PRIORITY_LABELS.get(key, _clean(value, "بدون اولویت"))


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
    value = task.get("tags")
    if isinstance(value, (list, tuple, set)):
        text = "، ".join(_clean(x) for x in value if _clean(x))
    else:
        text = _clean(value)
    return text or "بدون تگ"


def active_statuses(tasks: Iterable[dict]) -> list[str]:
    statuses: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status and status not in seen and is_active_status(status):
            seen.add(status)
            statuses.append(status)
    return statuses


def _draw_rtl(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float, align: str = "right") -> None:
    c.setFont(font, size)
    rendered = _rtl(text)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _draw_card(c: canvas.Canvas, task: dict, x: float, y: float, w: float, h: float, font: str, compact: bool) -> None:
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=1)

    priority = _normalise_status(task.get("priority"))
    accent = colors.HexColor(PRIORITY_COLORS.get(priority, "#94A3B8"))
    c.setFillColor(accent)
    c.roundRect(x, y, 1.7 * mm, h, 0.8 * mm, stroke=0, fill=1)

    pad = 3 * mm
    right = x + w - pad
    top = y + h - pad
    title = _short(task.get("title") or "بدون عنوان", 54 if not compact else 38)
    _draw_rtl(c, title, right, top - 1, font, 8.0 if not compact else 6.8)

    # Fixed vertical rhythm prevents metadata from touching or overlapping.
    line_gap = 5.0 * mm if not compact else 3.8 * mm
    meta_size = 6.0 if not compact else 5.1
    meta_y = top - (7.0 * mm if not compact else 5.2 * mm)
    _draw_rtl(c, f"دسته: {_short(_task_category(task), 22)}", right, meta_y, font, meta_size)
    _draw_rtl(c, f"اولویت: {_priority_label(task.get('priority'))}", right, meta_y - line_gap, font, meta_size)
    if not compact:
        _draw_rtl(c, f"مسئول: {_short(_task_assignee(task), 22)}", right, meta_y - 2 * line_gap, font, meta_size)
        _draw_rtl(c, f"موعد: {_short(_task_deadline(task), 22)}", right, meta_y - 3 * line_gap, font, meta_size)
        tags = _task_tags(task)
        if tags != "بدون تگ":
            _draw_rtl(c, f"تگ: {_short(tags, 28)}", right, meta_y - 4 * line_gap, font, 5.5)
    else:
        _draw_rtl(c, f"موعد: {_short(_task_deadline(task), 18)}", right, meta_y - 2 * line_gap, font, meta_size)


def build_kanban_pdf(tasks: list[dict]) -> BytesIO:
    statuses = active_statuses(tasks)
    if not statuses:
        raise ValueError("هیچ وضعیت فعال و واقعی برای ساخت کانبان برد وجود ندارد.")

    # Print-safe A4 landscape: 100% width, fixed margins, one page only.
    page_width, page_height = landscape(A4)
    margin_x = 7 * mm
    margin_top = 7 * mm
    margin_bottom = 6 * mm
    gap = 3 * mm
    title_h = 17 * mm
    header_h = 11 * mm
    board_bottom = margin_bottom + 5 * mm
    board_top = page_height - margin_top - title_h
    board_height = board_top - board_bottom
    font = _register_font()

    columns: dict[str, list[dict]] = {status: [] for status in statuses}
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status in columns:
            columns[status].append(task)
    for items in columns.values():
        items.sort(key=lambda t: (PRIORITY_ORDER.get(_normalise_status(t.get("priority")), 3), str(t.get("deadline") or "9999"), str(t.get("created_at") or ""), str(t.get("id") or "")))

    col_w = (page_width - 2 * margin_x - gap * (len(statuses) - 1)) / len(statuses)
    max_count = max((len(v) for v in columns.values()), default=1)
    card_gap = 2 * mm
    card_h = (board_height - header_h - card_gap * max(0, max_count - 1)) / max_count
    compact = card_h < 22 * mm
    if compact:
        card_h = max(11 * mm, card_h)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    c.setTitle("کانبان برد")
    c.setAuthor("Task Manager Bot")

    # Page background and title.
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    _draw_rtl(c, "کانبان برد وظایف", page_width - margin_x, page_height - margin_top - 5 * mm, font, 13)
    c.setFillColor(colors.HexColor("#64748B"))
    _draw_rtl(c, f"{sum(len(v) for v in columns.values())} وظیفه فعال  •  {len(statuses)} وضعیت", page_width - margin_x, page_height - margin_top - 11 * mm, font, 6.5)

    for index, status in enumerate(statuses):
        x = margin_x + index * (col_w + gap)
        items = columns[status]
        accent = colors.HexColor(STATUS_COLORS[index % len(STATUS_COLORS)])
        header_y = board_top - header_h

        # Column container.
        c.setFillColor(colors.HexColor("#F1F5F9"))
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.setLineWidth(0.55)
        c.roundRect(x, board_bottom, col_w, board_top - board_bottom, 3 * mm, stroke=1, fill=1)

        # Header stays fully inside the column.
        c.setFillColor(accent)
        c.roundRect(x, header_y, col_w, header_h, 3 * mm, stroke=0, fill=1)
        c.rect(x, header_y, col_w, 3 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        _draw_rtl(c, f"{_status_label(status)}  •  {len(items)}", x + col_w / 2, header_y + 3.6 * mm, font, 7.4, align="center")

        cards_top = header_y - card_gap
        for row, task in enumerate(items):
            y = cards_top - card_h - row * (card_h + card_gap)
            if y < board_bottom:
                continue
            # Equivalent of CSS break-inside/page-break-inside: avoid: every card is
            # an atomic ReportLab drawing operation and the board is emitted once.
            _draw_card(c, task, x + 2 * mm, y, col_w - 4 * mm, card_h, font, compact)

    c.setFillColor(colors.HexColor("#94A3B8"))
    _draw_rtl(c, "برد کانبان • نمای یک‌صفحه‌ای", margin_x, 2.8 * mm, font, 5.2, align="left")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
