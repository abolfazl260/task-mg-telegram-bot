from __future__ import annotations

import csv
import io
import arabic_reshaper
from bidi.algorithm import get_display
from .report_pdf_layout import render_pdf


def _kpi_rows(summary):
    """Export the same labeled KPI populations shown by the dashboard."""
    def rate(value):
        return "—" if value is None else f"{value}%"

    return [
        ("وظایف ایجادشده در بازه", summary.get("total", 0)),
        ("از وظایف ایجادشده، اکنون تکمیل", summary.get("done", 0)),
        ("از وظایف ایجادشده، اکنون در حال انجام", summary.get("in_progress", 0)),
        ("از وظایف ایجادشده، اکنون شروع‌نشده", summary.get("pending", 0)),
        ("از وظایف ایجادشده، اکنون لغوشده", summary.get("cancelled", 0)),
        ("تکمیل‌شده در بازه انتخابی", summary.get("completed_in_period", 0)),
        ("تکمیل‌شده دارای مهلت معتبر در بازه", summary.get("completed_with_deadline", 0)),
        ("نرخ تکمیل به‌موقع در بازه", rate(summary.get("on_time_rate"))),
        ("نرخ تکمیل با تأخیر در بازه", rate(summary.get("overdue_rate"))),
        (f"وظایف باز عقب‌افتاده تا {summary.get('backlog_as_of_utc') or 'امروز'} UTC",
         summary.get("overdue", 0)),
    ]


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
        for label, value in _kpi_rows(summary):
            writer.writerow([label, value])
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
        # Layout owns pagination only; authorization and full-filtered rows
        # remain the responsibility of the existing report route/service.
        return render_pdf(report, ReportExportService._rtl, _kpi_rows)


def export_report(report: dict, fmt: str) -> tuple[bytes, str, str]:
    if fmt == "csv": return ReportExportService.csv_bytes(report), "text/csv; charset=utf-8", "report.csv"
    if fmt == "pdf": return ReportExportService.pdf_bytes(report), "application/pdf", "report.pdf"
    raise ValueError("unsupported_export_format")
