from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import re

import arabic_reshaper
import jdatetime
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.date_service import user_today

PAGE_W, PAGE_H = landscape(A3)
BG = "#F8FAFC"
NAVY = "#1E293B"
BLUE = "#2563EB"
CELL_BORDER = "#CBD5E1"
WHITE = "#FFFFFF"
TEXT = "#0F172A"
MUTED = "#64748B"
BADGE_BG = "#F1F5F9"
BADGE_BORDER = "#E2E8F0"
WEEKDAYS = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه")
JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)


def _font_path() -> Path:
    candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("فونت یونیکد مناسب برای تولید PDF پیدا نشد.")


def _register_font() -> str:
    name = "CalendarUnicode"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(_font_path())))
    return name


def _rtl(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _clean_title(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip() or "بدون عنوان"


def _parse_deadline(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _truncate_to_width(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> str:
    """Ellipsize by measured PDF width so badges never overflow their cell."""
    text = _clean_title(text)
    if pdfmetrics.stringWidth(_rtl(text), font, size) <= max_width:
        return text
    suffix = "..."
    candidate = text
    while candidate and pdfmetrics.stringWidth(_rtl(candidate + suffix), font, size) > max_width:
        candidate = candidate[:-1].rstrip()
    return (candidate + suffix) if candidate else suffix


def _month_grid(year: int, month: int) -> list[list[jdatetime.date | None]]:
    first = jdatetime.date(year, month, 1)
    if month == 12:
        next_month = jdatetime.date(year + 1, 1, 1)
    else:
        next_month = jdatetime.date(year, month + 1, 1)
    days = (next_month - timedelta(days=1)).day
    leading = (first.weekday() - 5) % 7
    cells: list[jdatetime.date | None] = [None] * leading
    cells.extend(jdatetime.date(year, month, day) for day in range(1, days + 1))
    cells.extend([None] * ((7 - len(cells) % 7) % 7))
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


def _task_map(tasks: list[dict], year: int, month: int) -> dict[int, list[str]]:
    result: dict[int, list[str]] = defaultdict(list)
    for task in tasks:
        deadline = _parse_deadline(task.get("deadline"))
        if deadline is None:
            continue
        j = jdatetime.date.fromgregorian(date=deadline)
        if j.year == year and j.month == month:
            result[j.day].append(_clean_title(task.get("title")))
    return result


def _draw_rtl(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float, align: str = "right") -> None:
    rendered = _rtl(text)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _round_rect(c: canvas.Canvas, x: float, y: float, w: float, h: float, radius: float, fill: str, stroke: str | None = None, line_width: float = 0.6) -> None:
    c.setFillColor(colors.HexColor(fill))
    if stroke:
        c.setStrokeColor(colors.HexColor(stroke))
        c.setLineWidth(line_width)
        c.roundRect(x, y, w, h, radius, stroke=1, fill=1)
    else:
        c.roundRect(x, y, w, h, radius, stroke=0, fill=1)


def _draw_badge(c: canvas.Canvas, title: str, x: float, y: float, w: float, h: float, font: str) -> None:
    _round_rect(c, x, y, w, h, h / 2, BADGE_BG, BADGE_BORDER, 0.45)
    text = _truncate_to_width(c, title, font, 6.3, w - 5 * mm)
    _draw_rtl(c, text, x + w - 2.5 * mm, y + 2.35 * mm, font, 6.3)


def build_calendar_pdf(tasks: list[dict], user_id: int) -> BytesIO:
    """Build one A3 landscape page containing the user's current Jalali month."""
    today_gregorian = user_today(user_id)
    today_jalali = jdatetime.date.fromgregorian(date=today_gregorian)
    year, month = today_jalali.year, today_jalali.month
    weeks = _month_grid(year, month)
    tasks_by_day = _task_map(tasks, year, month)
    font = _register_font()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle(f"تقویم ماهانه {JALALI_MONTHS[month - 1]} {year}")
    c.setAuthor("Task Manager Bot")

    c.setFillColor(colors.HexColor(BG))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    margin_x = 14 * mm
    margin_top = 12 * mm
    margin_bottom = 12 * mm
    title_h = 17 * mm
    header_h = 12 * mm
    grid_top = PAGE_H - margin_top - title_h
    grid_bottom = margin_bottom
    grid_h = grid_top - grid_bottom
    header_gap = 4 * mm
    cells_top = grid_top - header_h - header_gap
    rows = len(weeks)
    row_gap = 3 * mm
    col_gap = 3 * mm
    grid_w = PAGE_W - 2 * margin_x
    col_w = (grid_w - col_gap * 6) / 7
    cell_h = (grid_h - header_gap - header_h - row_gap * (rows - 1)) / rows

    _draw_rtl(c, f"{JALALI_MONTHS[month - 1]} {year}", PAGE_W - margin_x, PAGE_H - margin_top - 6 * mm, font, 16)
    _draw_rtl(c, f"{sum(len(v) for v in tasks_by_day.values())} تسک دارای موعد", margin_x, PAGE_H - margin_top - 6 * mm, font, 7.2, align="left")

    for index, weekday in enumerate(WEEKDAYS):
        x = margin_x + (6 - index) * (col_w + col_gap)
        y = grid_top - header_h
        _round_rect(c, x, y, col_w, header_h, 4 * mm, NAVY)
        _draw_rtl(c, weekday, x + col_w / 2, y + 3.9 * mm, font, 7.1, align="center")

    badge_h = 7.2 * mm
    badge_gap = 2 * mm
    cell_pad_x = 3.5 * mm
    cell_pad_top = 4 * mm
    cell_pad_bottom = 3.5 * mm
    day_font_size = 9.5
    max_badges = max(0, int((cell_h - cell_pad_top - cell_pad_bottom - day_font_size * 0.3528 * mm - 4 * mm) // (badge_h + badge_gap)))

    for row_index, week in enumerate(weeks):
        y = cells_top - row_index * (cell_h + row_gap) - cell_h
        for index, day in enumerate(week):
            x = margin_x + (6 - index) * (col_w + col_gap)
            if day is None:
                _round_rect(c, x, y, col_w, cell_h, 3 * mm, "#F1F5F9", CELL_BORDER, 0.45)
                continue

            is_today = day.year == today_jalali.year and day.month == today_jalali.month and day.day == today_jalali.day
            border = BLUE if is_today else CELL_BORDER
            line_width = 1.35 if is_today else 0.55
            _round_rect(c, x, y, col_w, cell_h, 3 * mm, WHITE, border, line_width)
            _draw_rtl(c, str(day.day), x + col_w - cell_pad_x, y + cell_h - cell_pad_top - day_font_size * 0.3528 * mm, font, day_font_size)

            titles = tasks_by_day.get(day.day, [])
            visible = min(len(titles), max_badges)
            badge_w = col_w - 2 * cell_pad_x
            badge_y = y + cell_h - cell_pad_top - day_font_size * 0.3528 * mm - 6 * mm - badge_h
            for title in titles[:visible]:
                _draw_badge(c, title, x + cell_pad_x, badge_y, badge_w, badge_h, font)
                badge_y -= badge_h + badge_gap

            remaining = len(titles) - visible
            if remaining > 0:
                _draw_rtl(c, f"+{remaining} تسک دیگر", x + cell_pad_x, y + cell_pad_bottom, font, 6.1, align="left")

    c.save()
    buffer.seek(0)
    return buffer
