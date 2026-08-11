from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "بالا": 0, "متوسط": 1, "پایین": 2}
PRIORITY_LABELS = {"high": "بالا", "medium": "متوسط", "low": "پایین"}
PRIORITY_COLORS = {
    "high": "#DC2626",
    "medium": "#D97706",
    "low": "#16A34A",
    "بالا": "#DC2626",
    "متوسط": "#D97706",
    "پایین": "#16A34A",
}
VALID_STATUSES = ("pending", "in_progress", "done", "cancelled")
STATUS_LABELS = {
    "pending": "شروع‌نشده",
    "in_progress": "در حال انجام",
    "done": "انجام‌شده",
    "cancelled": "لغو شده",
}
STATUS_COLORS = {
    "pending": "#64748B",
    "in_progress": "#2563EB",
    "done": "#16A34A",
    "cancelled": "#DC2626",
}
TERMINAL_OR_INACTIVE = {
    "done", "completed", "complete", "closed", "close", "cancelled", "canceled",
    "rejected", "reject", "archived", "archive", "inactive", "disabled", "draft",
    "preparation", "preparing", "finished",
}

# A3 landscape canvas: 420 x 297 mm.
PAGE_MARGIN = 12 * mm
COLUMN_GAP = 8 * mm
CARD_GAP = 3 * mm
COLUMN_HEADER_HEIGHT = 12 * mm
TITLE_HEIGHT = 18 * mm
CARD_RADIUS = 4 * mm
CARD_BORDER = "#E2E8F0"
TITLE_COLOR = "#0F172A"
META_COLOR = "#475569"
CARD_PADDING_X = 6 * mm
CARD_PADDING_Y = 5 * mm
PRIORITY_STRIPE_WIDTH = 2.5 * mm

TITLE_SIZE = 8.5
META_SIZE = 6.7
LINE_HEIGHT_FACTOR = 1.45


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
        items.sort(
            key=lambda t: (
                PRIORITY_ORDER.get(_normalise_status(t.get("priority")), 3),
                str(t.get("deadline") or "9999"),
                str(t.get("created_at") or ""),
                str(t.get("id") or ""),
            )
        )
    return columns


def _draw_rtl(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    font: str,
    size: float,
    align: str = "right",
    color: colors.Color | None = None,
) -> None:
    c.setFont(font, size)
    if color is not None:
        c.setFillColor(color)
    rendered = _rtl(text)
    if align == "center":
        c.drawCentredString(x, y, rendered)
    elif align == "left":
        c.drawString(x, y, rendered)
    else:
        c.drawRightString(x, y, rendered)


def _task_lines(task: dict) -> list[tuple[str, float, colors.Color]]:
    """Return logical text lines before width-aware wrapping.

    Text is never truncated here. The renderer wraps each value into as many
    physical lines as required, keeping the requested font sizes unchanged.
    """
    lines: list[tuple[str, float, colors.Color]] = [
        (_clean(task.get("title"), "بدون عنوان") or "بدون عنوان", TITLE_SIZE, colors.HexColor(TITLE_COLOR)),
        (f"دسته: {_task_category(task)}", META_SIZE, colors.HexColor(META_COLOR)),
        (f"اولویت: {_priority_label(task.get('priority'))}", META_SIZE, colors.HexColor(META_COLOR)),
        (f"مسئول: {_task_assignee(task)}", META_SIZE, colors.HexColor(META_COLOR)),
        (f"موعد: {_task_deadline(task)}", META_SIZE, colors.HexColor(META_COLOR)),
    ]
    tags = _task_tags(task)
    if tags != "بدون تگ":
        lines.append((f"تگ: {tags}", META_SIZE, colors.HexColor(META_COLOR)))
    return lines


def _wrap_rtl(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Wrap Unicode RTL text without truncation.

    Wrapping happens on logical words, then each physical line is reshaped and
    bidi-reordered only when it is drawn. Long unbroken tokens are split by
    measured character width so they cannot overflow the card.
    """
    logical = _clean(text)
    if not logical:
        return [""]

    def fits(candidate: str) -> bool:
        return pdfmetrics.stringWidth(_rtl(candidate), font, size) <= max_width

    words = logical.split(" ")
    result: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if fits(candidate):
            current = candidate
            continue
        if current:
            result.append(current)
            current = ""
        if fits(word):
            current = word
            continue
        # A single token can still be wider than the card (URL, identifier, etc.).
        chunk = ""
        for char in word:
            candidate = chunk + char
            if chunk and not fits(candidate):
                result.append(chunk)
                chunk = char
            else:
                chunk = candidate
        current = chunk
    if current:
        result.append(current)
    return result or [""]


def _card_layout(task: dict, font: str, content_width: float) -> tuple[list[tuple[str, float, colors.Color]], float]:
    """Build physical lines and calculate the card's natural content height."""
    physical: list[tuple[str, float, colors.Color]] = []
    for text, size, color in _task_lines(task):
        for line in _wrap_rtl(text, font, size, content_width):
            physical.append((line, size, color))

    heights = [size * LINE_HEIGHT_FACTOR * 0.3528 * mm for _, size, _ in physical]
    line_gaps = 1.8 * mm
    natural_height = CARD_PADDING_Y * 2 + sum(heights) + line_gaps * max(0, len(physical) - 1)
    return physical, natural_height


def _natural_card_height(task: dict, compact: bool = False) -> float:
    """Compatibility helper; the actual PDF uses width-aware card layout."""
    # Kept for callers/tests that used the previous helper. It deliberately does
    # not perform any font shrinking or page-fit scaling.
    font = _register_font()
    content_width = 70 * mm
    _, height = _card_layout(task, font, content_width)
    return height


def _draw_card(
    c: canvas.Canvas,
    task: dict,
    x: float,
    y: float,
    w: float,
    h: float,
    font: str,
) -> None:
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor(CARD_BORDER))
    c.setLineWidth(0.55)
    c.roundRect(x, y, w, h, CARD_RADIUS, stroke=1, fill=1)

    priority = _normalise_status(task.get("priority"))
    c.setFillColor(colors.HexColor(PRIORITY_COLORS.get(priority, "#94A3B8")))
    c.roundRect(x, y, PRIORITY_STRIPE_WIDTH, h, 1.2 * mm, stroke=0, fill=1)

    content_width = w - CARD_PADDING_X * 2 - 1.5 * mm
    physical, natural_height = _card_layout(task, font, content_width)
    if h + 0.1 < natural_height:
        raise ValueError("ارتفاع کارت برای محتوای کامل کافی نیست؛ کارت نباید فشرده یا بریده شود.")

    right = x + w - CARD_PADDING_X
    current_y = y + h - CARD_PADDING_Y
    line_gap = 1.8 * mm
    for line, size, color in physical:
        line_height = size * LINE_HEIGHT_FACTOR * 0.3528 * mm
        baseline = current_y - line_height + 0.9 * mm
        _draw_rtl(c, line, right, baseline, font, size, color=color)
        current_y -= line_height + line_gap


def _draw_page_background(c: canvas.Canvas, page_width: float, page_height: float) -> None:
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.rect(0, 0, page_width, page_height, stroke=0, fill=1)


def _draw_board_header(c: canvas.Canvas, font: str, page_width: float, page_height: float, total: int, page_no: int) -> None:
    title_y = page_height - PAGE_MARGIN - 5.5 * mm
    _draw_rtl(c, "کانبان برد وظایف", page_width - PAGE_MARGIN, title_y, font, 13, color=colors.HexColor(TITLE_COLOR))
    _draw_rtl(
        c,
        f"{total} وظیفه  •  صفحه {page_no}",
        page_width - PAGE_MARGIN,
        page_height - PAGE_MARGIN - 12 * mm,
        font,
        6.7,
        color=colors.HexColor(META_COLOR),
    )


def _draw_column(
    c: canvas.Canvas,
    font: str,
    status: str,
    items: list[dict],
    start_index: int,
    x: float,
    board_top: float,
    board_bottom: float,
    col_w: float,
) -> int:
    """Draw as many complete cards as fit and return the next item index."""
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.setStrokeColor(colors.HexColor(CARD_BORDER))
    c.setLineWidth(0.55)
    c.roundRect(x, board_bottom, col_w, board_top - board_bottom, CARD_RADIUS, stroke=1, fill=1)

    header_y = board_top - COLUMN_HEADER_HEIGHT
    accent = colors.HexColor(STATUS_COLORS[status])
    c.setFillColor(accent)
    c.roundRect(x, header_y, col_w, COLUMN_HEADER_HEIGHT, CARD_RADIUS, stroke=0, fill=1)
    c.rect(x, header_y, col_w, 3 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    _draw_rtl(
        c,
        f"{STATUS_LABELS[status]}  •  {len(items)}",
        x + col_w / 2,
        header_y + 3.8 * mm,
        font,
        7.4,
        align="center",
    )

    inner_x = 3 * mm
    inner_w = col_w - 2 * inner_x
    current_y = header_y - CARD_GAP
    index = start_index

    while index < len(items):
        task = items[index]
        _, card_h = _card_layout(task, font, inner_w - CARD_PADDING_X * 2 - 1.5 * mm)
        if current_y - card_h < board_bottom:
            break
        _draw_card(c, task, x + inner_x, current_y - card_h, inner_w, card_h, font)
        current_y -= card_h + CARD_GAP
        index += 1

    if start_index == index and start_index < len(items):
        # A single card is larger than a whole board. Do not shrink it: fail
        # loudly rather than clipping or overlapping. Normal task cards fit A3.
        raise ValueError("یک کارت کانبان از ارتفاع قابل چاپ A3 بزرگ‌تر است و بدون کوچک‌سازی قابل رندر نیست.")

    if not items:
        c.setFillColor(colors.HexColor("#94A3B8"))
        _draw_rtl(c, "تسکی وجود ندارد", x + col_w / 2, header_y - 10 * mm, font, 6.2, align="center")
    return index


def build_kanban_pdf(tasks: list[dict]) -> BytesIO:
    """Render the Kanban board as an A3 landscape, naturally paginated PDF.

    The four status columns remain equal width on every page. Cards are never
    scaled down to make them fit; each column advances independently to the
    next page when its next complete card cannot fit vertically.
    """
    columns = _columns(tasks)
    page_width, page_height = landscape(A3)
    font = _register_font()

    col_w = (page_width - 2 * PAGE_MARGIN - COLUMN_GAP * 3) / 4
    board_top = page_height - PAGE_MARGIN - TITLE_HEIGHT
    board_bottom = PAGE_MARGIN

    total = sum(len(items) for items in columns.values())
    indexes = {status: 0 for status in VALID_STATUSES}

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    c.setTitle("کانبان برد")
    c.setAuthor("Task Manager Bot")

    page_no = 0
    while True:
        page_no += 1
        _draw_page_background(c, page_width, page_height)
        _draw_board_header(c, font, page_width, page_height, total, page_no)

        progress = False
        for column_index, status in enumerate(VALID_STATUSES):
            x = PAGE_MARGIN + column_index * (col_w + COLUMN_GAP)
            before = indexes[status]
            indexes[status] = _draw_column(
                c,
                font,
                status,
                columns[status],
                before,
                x,
                board_top,
                board_bottom,
                col_w,
            )
            progress = progress or indexes[status] != before

        c.setFillColor(colors.HexColor("#94A3B8"))
        _draw_rtl(
            c,
            f"برد کانبان  •  صفحه {page_no}",
            page_width - PAGE_MARGIN,
            PAGE_MARGIN / 2,
            font,
            5.2,
            color=colors.HexColor("#94A3B8"),
        )
        c.showPage()

        if all(indexes[status] >= len(columns[status]) for status in VALID_STATUSES):
            break
        if not progress:
            raise RuntimeError("رندر کانبان بدون پیشرفت متوقف شد؛ کارت‌ها نمی‌توانند بدون کوچک‌سازی در صفحه قرار بگیرند.")

    c.save()
    buffer.seek(0)
    return buffer
