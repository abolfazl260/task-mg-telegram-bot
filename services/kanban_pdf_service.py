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
VALID_STATUSES = ("pending", "in_progress", "done", "cancelled")
STATUS_LABELS = {"pending": "شروع‌نشده", "in_progress": "در حال انجام", "done": "انجام‌شده", "cancelled": "لغو شده"}
STATUS_COLORS = {"pending": "#64748B", "in_progress": "#2563EB", "done": "#16A34A", "cancelled": "#DC2626"}
TERMINAL_OR_INACTIVE = {"done", "completed", "complete", "closed", "close", "cancelled", "canceled", "rejected", "reject", "archived", "archive", "inactive", "disabled", "draft", "preparation", "preparing", "finished"}


def _normalise_status(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def is_active_status(value: object) -> bool:
    raw = str(value or "").strip()
    key = _normalise_status(raw)
    if not key or key in TERMINAL_OR_INACTIVE:
        return False
    if key in {"انجام‌شده", "انجام شده", "تکمیل‌شده", "تکمیل شده", "بسته", "لغو شده", "رد شده", "آماده‌سازی", "آماده سازی"}:
        return False
    if any(token in key for token in ("inactive", "disabled", "archived", "preparation", "preparing")):
        return False
    if any(token in raw for token in ("غیرفعال", "آماده‌سازی", "آماده سازی")):
        return False
    return True


def active_statuses(tasks: Iterable[dict]) -> list[str]:
    """Legacy helper retained for existing tests/callers; PDF columns use VALID_STATUSES."""
    statuses: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        status = str(task.get("status") or "").strip()
        if status and status not in seen and is_active_status(status):
            seen.add(status)
            statuses.append(status)
    return statuses


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


def _short_title(value: object, limit: int = 52) -> str:
    """Legacy title helper used by the existing test suite."""
    return _short(value, limit)


def _priority_label(value: object) -> str:
    return PRIORITY_LABELS.get(_normalise_status(value), _clean(value, "بدون اولویت"))


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


def _columns(tasks: Iterable[dict]) -> dict[str, list[dict]]:
    columns = {status: [] for status in VALID_STATUSES}
    for task in tasks:
        status = _normalise_status(task.get("status"))
        if status in columns:
            columns[status].append(task)
    for items in columns.values():
        items.sort(key=lambda t: (PRIORITY_ORDER.get(_normalise_status(t.get("priority")), 3), str(t.get("deadline") or "9999"), str(t.get("created_at") or ""), str(t.get("id") or "")))
    return columns


def _draw_rtl(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float, align: str = "right") -> None:
    c.setFont(font, size)
    rendered = _rtl(text)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _card_lines(task: dict, compact: bool) -> list[tuple[str, float]]:
    value_limit = 18 if compact else 25
    lines = [
        (_short(task.get("title") or "بدون عنوان", 42 if compact else 58), 6.9 if compact else 8.0),
        (f"دسته: {_short(_task_category(task), value_limit)}", 5.1 if compact else 6.0),
        (f"اولویت: {_priority_label(task.get('priority'))}", 5.1 if compact else 6.0),
        (f"مسئول: {_short(_task_assignee(task), value_limit)}", 5.1 if compact else 6.0),
        (f"موعد: {_short(_task_deadline(task), value_limit)}", 5.1 if compact else 6.0),
    ]
    tags = _task_tags(task)
    if tags != "بدون تگ":
        lines.append((f"تگ: {_short(tags, 20 if compact else 30)}", 5.2 if compact else 5.5))
    return lines


def _natural_card_height(task: dict, compact: bool) -> float:
    # Content-driven height equivalent to padding:12px 16px, line-height:1.5 and margin-bottom:6px.
    pad_y = 4.23 * mm
    margin_bottom = 2.12 * mm
    return pad_y * 2 + sum(size * 1.5 * 0.3528 * mm + margin_bottom for _, size in _card_lines(task, compact))


def _draw_card(c: canvas.Canvas, task: dict, x: float, y: float, w: float, h: float, font: str, compact: bool) -> None:
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=1)
    priority = _normalise_status(task.get("priority"))
    c.setFillColor(colors.HexColor(PRIORITY_COLORS.get(priority, "#94A3B8")))
    c.roundRect(x, y, 1.7 * mm, h, 0.8 * mm, stroke=0, fill=1)

    pad_x = 5.64 * mm
    pad_y = 4.23 * mm
    right = x + w - pad_x
    current_y = y + h - pad_y
    margin_bottom = 2.12 * mm
    for text, size in _card_lines(task, compact):
        line_h = size * 1.5 * 0.3528 * mm
        _draw_rtl(c, text, right, current_y - line_h + 1.0 * mm, font, size)
        current_y -= line_h + margin_bottom


def build_kanban_pdf(tasks: list[dict]) -> BytesIO:
    columns = _columns(tasks)
    page_width, page_height = landscape(A4)
    margin_x = 7 * mm
    margin_top = 7 * mm
    margin_bottom = 7 * mm
    gap = 4 * mm
    title_h = 17 * mm
    header_h = 11 * mm
    board_top = page_height - margin_top - title_h
    board_bottom = margin_bottom + 4 * mm
    board_height = board_top - board_bottom
    font = _register_font()

    # Flex-grid equivalent: four equal flex:1 columns with min-width:0.
    col_w = (page_width - 2 * margin_x - gap * 3) / 4
    inner_x = 2.5 * mm
    inner_w = col_w - 2 * inner_x
    card_gap = 2.2 * mm
    max_count = max((len(v) for v in columns.values()), default=1)
    compact = max_count >= 6
    available_h = board_height - header_h - card_gap
    natural_totals = [sum(_natural_card_height(task, compact) for task in items) + card_gap * max(0, len(items) - 1) for items in columns.values()]
    scale = min(1.0, available_h / max(natural_totals, default=available_h)) if natural_totals else 1.0
    scale = max(scale, 0.52)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    c.setTitle("کانبان برد")
    c.setAuthor("Task Manager Bot")
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    _draw_rtl(c, "کانبان برد وظایف", page_width - margin_x, page_height - margin_top - 5 * mm, font, 13)
    _draw_rtl(c, f"{sum(len(v) for v in columns.values())} وظیفه  •  ۴ وضعیت", page_width - margin_x, page_height - margin_top - 11 * mm, font, 6.5)

    for index, status in enumerate(VALID_STATUSES):
        items = columns[status]
        x = margin_x + index * (col_w + gap)
        header_y = board_top - header_h
        accent = colors.HexColor(STATUS_COLORS[status])
        c.setFillColor(colors.HexColor("#F1F5F9"))
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.setLineWidth(0.55)
        c.roundRect(x, board_bottom, col_w, board_top - board_bottom, 3 * mm, stroke=1, fill=1)
        c.setFillColor(accent)
        c.roundRect(x, header_y, col_w, header_h, 3 * mm, stroke=0, fill=1)
        c.rect(x, header_y, col_w, 3 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        _draw_rtl(c, f"{STATUS_LABELS[status]}  •  {len(items)}", x + col_w / 2, header_y + 3.6 * mm, font, 7.2, align="center")

        current_y = header_y - card_gap
        for task in items:
            card_h = max(9 * mm, _natural_card_height(task, compact) * scale)
            if current_y - card_h < board_bottom:
                card_h = max(9 * mm, current_y - board_bottom)
            if card_h <= 0:
                break
            _draw_card(c, task, x + inner_x, current_y - card_h, inner_w, card_h, font, compact)
            current_y -= card_h + card_gap
        if not items:
            c.setFillColor(colors.HexColor("#94A3B8"))
            _draw_rtl(c, "تسکی وجود ندارد", x + col_w / 2, header_y - 10 * mm, font, 6.2, align="center")

    c.setFillColor(colors.HexColor("#94A3B8"))
    _draw_rtl(c, "برد کانبان • نمای یک‌صفحه‌ای", margin_x, 2.8 * mm, font, 5.2, align="left")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
