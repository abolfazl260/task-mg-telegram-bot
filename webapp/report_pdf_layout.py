"""Bounded, page-aware ReportLab layout for authorized web-report PDF exports.

The caller supplies already-filtered dashboard rows. This module does not
query the database or change the report-token/CSV authorization contract.
"""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_NAME = "TaskMGReportUnicode"
FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN = 28
FOOTER_LIMIT = 53
CELL_FONT_SIZE = 8
CELL_LINE_HEIGHT = 11.5
MAX_CELL_CHARS = 1024

# Right-to-left column order. Sum equals page width minus both margins.
COLUMN_WIDTHS = (80, 216, 84, 84, 92, 104, PAGE_WIDTH - 2 * MARGIN - 660)
COLUMNS = (
    ("id", "شناسه", 2),
    ("title", "عنوان", 4),
    ("status_label", "وضعیت", 2),
    ("priority_label", "اولویت", 2),
    ("deadline", "مهلت", 2),
    ("category", "دسته‌بندی", 3),
    ("assignee", "مسئول", 3),
)


def _unicode_font() -> str:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME
    for path in FONT_PATHS:
        if not Path(path).is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            return FONT_NAME
        except (OSError, ValueError):
            continue
    # Helvetica cannot render Persian; fail rather than generating unreadable
    # exports with dropped glyphs. HTTP layer emits a sanitized 500.
    raise RuntimeError("pdf_unicode_font_unavailable")


def _cell_lines(value, font: str, size: float, width: float, limit: int, rtl) -> list[str]:
    """Wrap on rendered glyph widths, hard-break long identifiers, mark clipping."""
    source = re.sub(r"\s+", " ", str(value if value is not None else "")).strip() or "—"
    if len(source) > MAX_CELL_CHARS:
        source = source[:MAX_CELL_CHARS].rstrip() + "…"

    def fits(chunk: str) -> bool:
        return pdfmetrics.stringWidth(rtl(chunk), font, size) <= width

    lines: list[str] = []
    current = ""
    for token in source.split(" "):
        candidate = f"{current} {token}" if current else token
        if fits(candidate):
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while token:
            if fits(token):
                current = token
                break
            low, high, best = 1, len(token), 0
            while low <= high:
                mid = (low + high) // 2
                if fits(token[:mid]):
                    best = mid
                    low = mid + 1
                else:
                    high = mid - 1
            split = best or 1
            lines.append(token[:split])
            token = token[split:]
    if current:
        lines.append(current)
    if not lines:
        lines = ["—"]
    if len(lines) > limit:
        lines = lines[:limit]
        last = lines[-1].rstrip()
        while last and not fits(last + "…"):
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


def render_pdf(report: dict, rtl, kpi_rows) -> bytes:
    """Render a landscape PDF with repeated headers and measured rows."""
    font = _unicode_font()
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=1)
    pdf.setTitle("TaskMG Web Report")
    pdf.setAuthor("TaskMG")

    right_edge = PAGE_WIDTH - MARGIN
    page_number = 1
    column_edges = []
    edge = right_edge
    for width in COLUMN_WIDTHS:
        column_edges.append(edge)
        edge -= width

    def print_text(x: float, y: float, value, size: float, *, right: bool = True):
        pdf.setFont(font, size)
        shown = rtl(str(value))
        if right:
            pdf.drawRightString(x, y, shown)
        else:
            pdf.drawString(x, y, shown)

    def footer():
        pdf.setStrokeColorRGB(.84, .85, .87)
        pdf.line(MARGIN, 42, right_edge, 42)
        pdf.setFillColorRGB(.42, .44, .48)
        print_text(right_edge, 28, f"Page {page_number}", 8)
        pdf.setFillColorRGB(0, 0, 0)

    def table_header(top: float) -> float:
        height = 27
        pdf.setFillColorRGB(.93, .95, .97)
        pdf.rect(MARGIN, top - height, PAGE_WIDTH - 2 * MARGIN, height, stroke=0, fill=1)
        pdf.setFillColorRGB(.15, .21, .28)
        for idx, (_, title, _) in enumerate(COLUMNS):
            print_text(column_edges[idx] - 7, top - 18, title, 9)
        pdf.setStrokeColorRGB(.79, .82, .85)
        pdf.line(MARGIN, top - height, right_edge, top - height)
        pdf.setFillColorRGB(0, 0, 0)
        return top - height

    def page_header(first: bool) -> float:
        pdf.setFillColorRGB(.11, .16, .23)
        print_text(right_edge, PAGE_HEIGHT - 35, "گزارش وظایف", 15)
        pdf.setFillColorRGB(.43, .45, .5)
        period = report.get("period", {}).get("gregorian") or date.today().isoformat()
        period_text = _cell_lines(period, font, 9, PAGE_WIDTH - 2 * MARGIN, 1, rtl)[0]
        print_text(right_edge, PAGE_HEIGHT - 54, period_text, 9)
        if first:
            summary = report.get("summary") or {}
            pdf.setFillColorRGB(.12, .18, .24)
            print_text(right_edge, PAGE_HEIGHT - 82, "شاخص‌های گزارش", 10)
            columns = list(kpi_rows(summary))
            for index, (label, value) in enumerate(columns):
                col, row = divmod(index, 5)
                block_right = right_edge - col * ((PAGE_WIDTH - 2 * MARGIN) / 2)
                available_width = (PAGE_WIDTH - 2 * MARGIN) / 2 - 20
                content = f"{label}: {value}"
                visible = _cell_lines(content, font, 8.2, available_width, 2, rtl)
                baseline = PAGE_HEIGHT - 101 - row * 20
                for n, line in enumerate(visible):
                    print_text(block_right - 7, baseline - n * 9, line, 8.2)
            return table_header(PAGE_HEIGHT - 230)
        print_text(right_edge, PAGE_HEIGHT - 79, "ادامه فهرست وظایف", 9)
        return table_header(PAGE_HEIGHT - 96)

    y = page_header(first=True)
    rows = report.get("rows") or []
    for index, item in enumerate(rows):
        columns = []
        for key, _, max_lines in COLUMNS:
            value = item.get(key, "")
            if key == "priority_label" and not value:
                value = item.get("priority", "")
            column_index = len(columns)
            width = COLUMN_WIDTHS[column_index] - 14
            columns.append(_cell_lines(value, font, CELL_FONT_SIZE, width, max_lines, rtl))
        line_count = max(len(lines) for lines in columns)
        row_height = max(28, line_count * CELL_LINE_HEIGHT + 11)
        if y - row_height < FOOTER_LIMIT:
            footer()
            pdf.showPage()
            page_number += 1
            y = page_header(first=False)

        if index % 2:
            pdf.setFillColorRGB(.974, .981, .99)
            pdf.rect(MARGIN, y - row_height, PAGE_WIDTH - 2 * MARGIN, row_height, fill=1, stroke=0)
        pdf.setFillColorRGB(.15, .18, .22)
        for col_index, lines in enumerate(columns):
            for line_index, line in enumerate(lines):
                print_text(
                    column_edges[col_index] - 7,
                    y - 12 - CELL_LINE_HEIGHT * line_index,
                    line, CELL_FONT_SIZE,
                )
        pdf.setStrokeColorRGB(.88, .89, .91)
        pdf.line(MARGIN, y - row_height, right_edge, y - row_height)
        y -= row_height

    if not rows:
        print_text(right_edge - 7, y - 19, "وظیفه‌ای برای این گزارش وجود ندارد.", 9)
    footer()
    pdf.save()
    return output.getvalue()
