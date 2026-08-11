from __future__ import annotations
from io import BytesIO
from pathlib import Path
from datetime import datetime

import jdatetime
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

def _font_path() -> Path | None:
    # 1. ابتدا تلاش می‌کند فونت را از پوشه fonts داخل پروژه بخواند
    project_root = Path(__file__).resolve().parent.parent
    local_font = project_root / "fonts" / "Vazirmatn.ttf"
    if local_font.exists():
        return local_font
        
    # 2. اگر فونت لوکال نبود، مسیرهای سیستم‌عامل را می‌گردد
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None

def _register_font() -> str:
    name = "CalendarUnicode"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
        
    font_p = _font_path()
    if font_p:
        try:
            pdfmetrics.registerFont(TTFont(name, str(font_p)))
            return name
        except Exception:
            pass
    return "Helvetica"

def _rtl(text: object) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(value))
    except Exception:
        return value

def _draw_rtl(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float, align: str = "right", fill_color=colors.HexColor("#0F172A")) -> None:
    c.setFont(font, size)
    c.setFillColor(fill_color)
    rendered = _rtl(text) if font != "Helvetica" else str(text)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)

def _parse_gregorian_date(deadline_str: str):
    if not deadline_str:
        return None
    clean_str = str(deadline_str).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except Exception:
            continue
    return None

# نکته کلیدی: پارامتر user_id اضافه شد تا با فایل main.py و هندلر شما سازگار باشد
def build_calendar_pdf(tasks: list[dict], user_id=None) -> BytesIO:
    # 1. تقویم همیشه روی ماه جاری شمسی تنظیم می‌شود
    today_j = jdatetime.date.today()
    year, month = today_j.year, today_j.month

    # 2. فقط تسک‌های دارای ددلاین در همین ماه را استخراج می‌کنیم
    task_by_jday: dict[int, list[dict]] = {}
    for task in tasks:
        # تسک‌های لغو شده وارد تقویم نشوند
        if task.get("status") == "cancelled":
            continue
            
        d = _parse_gregorian_date(task.get("deadline"))
        if not d:
            continue
            
        j_date = jdatetime.date.fromgregorian(date=d)
        if j_date.year == year and j_date.month == month:
            task_by_jday.setdefault(j_date.day, []).append(task)

    # 3. راه‌اندازی صفحه (A3 برای فضای بزرگتر و مدرن)
    page_width, page_height = landscape(A3)
    margin_x = 12 * mm
    margin_top = 15 * mm
    margin_bottom = 12 * mm
    title_area_h = 22 * mm
    
    font = _register_font()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    c.setTitle("تقویم ماهانه تسک‌ها")

    # Background
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    # Title Banner
    month_name = jdatetime.date(year, month, 1).j_months_fa[month - 1]
    main_title = f"تقویم ماهانه پروژه‌ها - {month_name} {year}"
    _draw_rtl(c, main_title, page_width - margin_x, page_height - margin_top, font, 18, align="right", fill_color=colors.HexColor("#0F172A"))
    
    total_in_month = sum(len(v) for v in task_by_jday.values())
    sub_title = f"تعداد کل تسک‌های این ماه: {total_in_month}"
    _draw_rtl(c, sub_title, page_width - margin_x, page_height - margin_top - 7 * mm, font, 10, align="right", fill_color=colors.HexColor("#64748B"))

    # Grid Setup
    weekdays_fa = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
    grid_top = page_height - margin_top - title_area_h
    grid_bottom = margin_bottom
    grid_w = page_width - 2 * margin_x
    col_w = grid_w / 7
    header_h = 12 * mm
    
    # Weekday Headers (RTL order: Saturday on far right)
    for i, day_name in enumerate(weekdays_fa):
        x = page_width - margin_x - (i + 1) * col_w
        c.setFillColor(colors.HexColor("#1E293B"))
        c.roundRect(x + 1*mm, grid_top - header_h, col_w - 2*mm, header_h, 2*mm, stroke=0, fill=1)
        _draw_rtl(c, day_name, x + col_w / 2, grid_top - header_h + 3.5 * mm, font, 11, align="center", fill_color=colors.white)

    # Build days grid for Jalali month
    first_jdate = jdatetime.date(year, month, 1)
    first_gdate = first_jdate.togregorian()
    first_day_col = (first_gdate.weekday() - 5) % 7
    
    days_in_month = 30 if month > 6 else 31
    if month == 12:
        days_in_month = 30 if first_jdate.isleap() else 29

    weeks = [[]]
    weeks[0] = [None] * first_day_col
    for day in range(1, days_in_month + 1):
        if len(weeks[-1]) == 7:
            weeks.append([])
        weeks[-1].append(day)
    while len(weeks[-1]) < 7:
        weeks[-1].append(None)

    num_weeks = len(weeks)
    available_h = grid_top - header_h - grid_bottom - 4*mm
    row_h = available_h / num_weeks

    # Render Month Grid Cells
    for row_idx, week in enumerate(weeks):
        y = grid_top - header_h - (row_idx + 1) * row_h
        for col_idx, day in enumerate(week):
            x = page_width - margin_x - (col_idx + 1) * col_w
            cell_x = x + 1 * mm
            cell_w = col_w - 2 * mm
            cell_h = row_h - 2 * mm

            if day is None:
                c.setFillColor(colors.HexColor("#F1F5F9"))
                c.setStrokeColor(colors.HexColor("#E2E8F0"))
                c.setLineWidth(0.5)
                c.roundRect(cell_x, y + 1*mm, cell_w, cell_h, 3*mm, stroke=1, fill=1)
                continue

            is_today = (year == today_j.year and month == today_j.month and day == today_j.day)
            bg_color = colors.HexColor("#FFFFFF")
            border_color = colors.HexColor("#2563EB") if is_today else colors.HexColor("#CBD5E1")
            
            c.setFillColor(bg_color)
            c.setStrokeColor(border_color)
            c.setLineWidth(1.2 if is_today else 0.6)
            c.roundRect(cell_x, y + 1*mm, cell_w, cell_h, 3*mm, stroke=1, fill=1)

            # Day Number Header
            num_color = colors.HexColor("#2563EB") if is_today else colors.HexColor("#0F172A")
            _draw_rtl(c, str(day), cell_x + cell_w - 3*mm, y + cell_h - 6*mm, font, 11, align="right", fill_color=num_color)

            # Render Task Titles
            day_tasks = task_by_jday.get(day, [])
            if day_tasks:
                task_y = y + cell_h - 12 * mm
                max_tasks_visible = max(1, int((cell_h - 14 * mm) / (5.5 * mm)))
                
                for t_idx, task in enumerate(day_tasks[:max_tasks_visible]):
                    title = str(task.get("title", "بدون عنوان")).strip()
                    if len(title) > 20:
                        title = title[:18] + "..."
                    
                    # Task background pill
                    c.setFillColor(colors.HexColor("#E2E8F0"))
                    c.roundRect(cell_x + 2*mm, task_y - 1*mm, cell_w - 4*mm, 5*mm, 1.5*mm, stroke=0, fill=1)
                    
                    # Task text (Dark color)
                    _draw_rtl(c, f"• {title}", cell_x + cell_w - 3*mm, task_y, font, 8, align="right", fill_color=colors.HexColor("#0F172A"))
                    task_y -= 5.8 * mm

                if len(day_tasks) > max_tasks_visible:
                    more_count = len(day_tasks) - max_tasks_visible
                    _draw_rtl(c, f"+{more_count} تسک دیگر", cell_x + 3*mm, y + 2*mm, font, 7.5, align="left", fill_color=colors.HexColor("#2563EB"))

    c.save()
    buffer.seek(0)
    return buffer
