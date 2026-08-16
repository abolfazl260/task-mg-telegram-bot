from webapp.report_export import export_report


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
