def test_monthly_calendar_pdf_callback_data_is_distinct():
    """Keep the PDF export callback separate from the generic report callback."""
    assert "report_calendar_pdf" != "report_calendar"
