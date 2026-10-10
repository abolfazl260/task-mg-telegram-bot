"""CSV and PDF export regression tests, including rendered-layout geometry."""

import re
from collections import Counter

import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdf_canvas

from webapp import report_pdf_layout as layout
from webapp.report_export import ReportExportService, export_report


def _report():
    return {
        "period": {"gregorian": "2026-08-01 تا 2026-08-31"},
        "summary": {"total": 2, "done": 1, "in_progress": 1, "pending": 0, "cancelled": 0},
        "rows": [{"id": "T-1", "title": "تست فارسی", "status_label": "انجام‌شده", "priority_label": "بالا", "deadline": "2026-08-10", "category": "عمومی", "assignee": "کاربر"}],
    }


def test_csv_export_has_excel_utf8_bom():
    payload, content_type, filename = export_report(_report(), "csv")
    assert payload.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in content_type
    assert filename == "report.csv"
    assert "تست فارسی" in payload.decode("utf-8-sig")


def test_pdf_export_returns_pdf_document():
    payload, content_type, filename = export_report(_report(), "pdf")
    assert payload.startswith(b"%PDF")
    assert content_type == "application/pdf"
    assert filename == "report.pdf"


def _many_rows(n=180):
    report = _report()
    report["summary"]["total"] = n
    report["rows"] = [
        {
            "id": f"ROW-{index:04d}",
            "title": "عنوان بسیار بلند فارسی همراه با Mixed English details " * 6
                     + f" - مورد شماره {index}",
            "status_label": "در حال انجام",
            "priority_label": "خیلی مهم و فوری",
            "deadline": "2026-08-30",
            "category": "دسته‌بندی نام بسیار بلند با مشخصات اضافی",
            "assignee": "کاربر نمونه Persian User " * 8,
        }
        for index in range(n)
    ]
    return report


def _record_canvas(monkeypatch):
    created = []

    class RecordingCanvas(pdf_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.recorded = []
            self.finished_pages = 0
            created.append(self)

        def drawRightString(self, x, y, text, *args, **kwargs):
            self.recorded.append((self._pageNumber, x, y, text, self._fontname, self._fontsize))
            return super().drawRightString(x, y, text, *args, **kwargs)

        def showPage(self):
            self.finished_pages += 1
            return super().showPage()

    monkeypatch.setattr(layout.canvas, "Canvas", RecordingCanvas)
    return created


def test_pdf_repeats_column_headers_and_rows_on_every_page(monkeypatch):
    canvases = _record_canvas(monkeypatch)
    report = _many_rows(140)
    pdf, content_type, name = export_report(report, "pdf")
    assert pdf.startswith(b"%PDF")
    assert content_type == "application/pdf" and name == "report.pdf"
    recorded = canvases[0]
    assert recorded.finished_pages >= 3
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == recorded.finished_pages
    for heading in ("شناسه", "عنوان", "وضعیت", "اولویت", "مهلت", "دسته‌بندی", "مسئول"):
        shaped = ReportExportService._rtl(heading)
        pages = {page for page, _, _, text, _, _ in recorded.recorded if text == shaped}
        assert pages == set(range(1, recorded.finished_pages + 1))
    # Each task identifier is drawn exactly once, even across page breaks.
    all_cells = Counter(str(entry[3]) for entry in recorded.recorded)
    for index in range(140):
        assert all_cells[f"ROW-{index:04d}"] == 1
    # Every page has a page-number footer and repeated date/column context.
    for number in range(1, recorded.finished_pages + 1):
        assert all_cells[f"Page {number}"] == 1
    assert all(
        layout.MARGIN <= x <= layout.PAGE_WIDTH - layout.MARGIN
        and (y >= layout.FOOTER_LIMIT or y == 28)
        for _, x, y, _, _, _ in recorded.recorded
    )


def test_pdf_wrapping_measures_glyph_width_and_marks_long_value_truncation():
    font = layout._unicode_font()
    rtl = ReportExportService._rtl
    full = "آزمایش متن فارسی Mixed English123 بسیار بلند " * 35
    lines = layout._cell_lines(full, font, 8, 145, 4, rtl)
    assert 1 <= len(lines) <= 4
    assert lines[-1].endswith("…")
    assert all(pdfmetrics.stringWidth(rtl(x), font, 8) <= 145 for x in lines)
    # A single overlong token must also wrap without crossing the column edge.
    long_id = "task-extremely-long-id-" * 80
    id_lines = layout._cell_lines(long_id, font, 8, 55, 2, rtl)
    assert len(id_lines) == 2 and id_lines[-1].endswith("…")
    assert all(pdfmetrics.stringWidth(rtl(x), font, 8) <= 55 for x in id_lines)


@pytest.mark.parametrize("n", [0, 1, 30, 200])
def test_pdf_supports_empty_single_and_many_row_reports(n):
    payload = export_report(_many_rows(n), "pdf")[0]
    assert payload.startswith(b"%PDF")
    assert payload.endswith(b"%%EOF\n")


def test_pdf_missing_unicode_font_fails_explicitly_not_helvetica(monkeypatch):
    monkeypatch.setattr(layout, "FONT_PATHS", ("/no/such/persian-font.ttf",))
    monkeypatch.setattr(layout.pdfmetrics, "getRegisteredFontNames", list)
    with pytest.raises(RuntimeError, match="pdf_unicode_font_unavailable"):
        export_report(_report(), "pdf")


def test_pdf_persian_glyphs_are_shaped_and_csv_remains_full_fidelity():
    rtl = ReportExportService._rtl
    assert rtl("تست فارسی") != "تست فارسی"
    report = _many_rows(70)
    pdf = export_report(report, "pdf")[0]
    csv_data = export_report(report, "csv")[0].decode("utf-8-sig")
    assert pdf.startswith(b"%PDF")
    assert csv_data.count("ROW-") == 70
    assert "عنوان بسیار بلند فارسی" in csv_data
