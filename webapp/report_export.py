from __future__ import annotations

import csv
import io
from datetime import date

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


class ReportExportService:
    """Format report data without coupling HTTP handlers to export details."""

    @staticmethod
    def csv_bytes(report: dict) -> bytes:
        rows = report.get("rows") or []
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["گزارش وظایف"])
        writer.writerow(["تاریخ گزارش", report.get("period", {}).get("gregorian", "")])
        summary = report.get("summary", {})
        writer.writerow([])
        writer.writerow(["شاخص", "مقدار"])
        writer.writerow(["کل وظایف", summary.get("total", 0)])
        writer.writerow(["انجام‌شده", summary.get("done", 0)])
        writer.writerow(["در حال انجام", summary.get("in_progress", 0)])
        writer.writerow(["شروع‌نشده", summary.get("pending", 0)])
        writer.writerow(["لغوشده", summary.get("cancelled", 0)])
        writer.writerow([])
        writer.writerow(["شناسه", "عنوان", "وضعیت", "اولویت", "مهلت", "دسته‌بندی", "مسئول"])
        for row in rows:
            writer.writerow([row.get("id", ""), row.get("title", ""), row.get("status_label", ""), row.get("priority_label", row.get("priority", "")), row.get("deadline", ""), row.get("category", ""), row.get("assignee", "")])
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    @staticmethod
    def _rtl(value) -> str:
        text = str(value or "").replace("\n", " ")
        return get_display(arabic_reshaper.reshape(text)) if any("\u0600" <= char <= "\u06ff" for char in text) else text

    @staticmethod
    def pdf_bytes(report: dict) -> bytes:
        output = io.BytesIO(); page = landscape(A4); pdf = canvas.Canvas(output, pagesize=page); width, height = page
        font_name = "Helvetica"
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"):
            try:
                pdfmetrics.registerFont(TTFont("ReportFont", path)); font_name = "ReportFont"; break
            except Exception:
                continue
        text = ReportExportService._rtl
        pdf.setFont(font_name, 16); pdf.drawString(36, height - 40, text("گزارش وظایف"))
        pdf.setFont(font_name, 9); pdf.drawString(36, height - 58, text(report.get("period", {}).get("gregorian", date.today().isoformat())))
        summary = report.get("summary", {}); y = height - 85
        for label, value in [("کل وظایف", summary.get("total", 0)), ("انجام‌شده", summary.get("done", 0)), ("در حال انجام", summary.get("in_progress", 0)), ("شروع‌نشده", summary.get("pending", 0)), ("لغوشده", summary.get("cancelled", 0))]:
            pdf.drawString(36, y, text(f"{label}: {value}")); y -= 14
        y -= 5; pdf.setFont(font_name, 8)
        headers = ["شناسه", "عنوان", "وضعیت", "اولویت", "مهلت", "دسته‌بندی", "مسئول"]; x_positions = [36, 100, 330, 410, 475, 555, 635]
        for x, header in zip(x_positions, headers): pdf.drawString(x, y, text(header))
        y -= 14
        for row in (report.get("rows") or []):
            values = [row.get("id", ""), row.get("title", ""), row.get("status_label", ""), row.get("priority_label", row.get("priority", "")), row.get("deadline", ""), row.get("category", ""), row.get("assignee", "")]
            for x, value in zip(x_positions, values): pdf.drawString(x, y, text(str(value)[:30]))
            y -= 12
            if y < 30:
                pdf.showPage(); pdf.setFont(font_name, 8); y = height - 35
        pdf.save(); return output.getvalue()


def export_report(report: dict, fmt: str) -> tuple[bytes, str, str]:
    if fmt == "csv": return ReportExportService.csv_bytes(report), "text/csv; charset=utf-8", "report.csv"
    if fmt == "pdf": return ReportExportService.pdf_bytes(report), "application/pdf", "report.pdf"
    raise ValueError("unsupported_export_format")
