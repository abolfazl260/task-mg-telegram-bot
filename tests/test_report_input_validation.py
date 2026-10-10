"""Regression coverage for Web Report input limits and HTTP error boundaries (#223)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from webapp import report_dashboard_service as dashboard
from webapp import report_routes
from tests.test_http_error_sanitization import _FakeHandler


def response(path, monkeypatch, *, dashboard_fn=None, export_fn=None):
    fake_report = dashboard_fn or Mock(return_value={"report_type": "dashboard", "rows": [], "summary": {}})
    monkeypatch.setattr(report_routes, "dashboard_report", fake_report)
    if export_fn is not None:
        monkeypatch.setattr(report_routes, "export_report", export_fn)
    handler = _FakeHandler(path)
    assert report_routes.handle_report_api(handler)
    return handler, fake_report


@pytest.mark.parametrize(("query", "code"), [
    ("page=abc", "invalid_report_page"),
    ("page=", "invalid_report_page"),
    ("page=%ZZ", "invalid_report_page"),
    ("page=%E0%A4%A", "invalid_report_page"),
    ("page=1.2", "invalid_report_page"),
    ("page=0", "invalid_report_page"),
    ("page=-1", "invalid_report_page"),
    ("page=%2B1", "invalid_report_page"),
    ("page=10001", "invalid_report_page"),
    ("page=" + "9" * 5000, "invalid_report_page"),
    ("period=custom", "invalid_report_date"),
    ("period=custom&start=2026-08-01", "invalid_report_date"),
    ("period=custom&start=&end=2026-08-01", "invalid_report_date"),
    ("period=custom&start=not-a-date&end=2026-08-01", "invalid_report_date"),
    ("period=custom&start=2026-02-30&end=2026-08-01", "invalid_report_date"),
    ("period=custom&start=2026-08-01T00%3A00%3A00&end=2026-08-31", "invalid_report_date"),
    ("period=custom&start=%FF&end=2026-08-31", "invalid_report_date"),
    ("period=unknown", "invalid_report_period"),
    ("period=", "invalid_report_period"),
    ("period=custom&start=2024-01-01&end=2025-01-01", "report_period_too_large"),
    ("period=custom&start=1900-01-01&end=1899-12-31", "report_date_out_of_range"),
    ("period=custom&start=2101-01-01&end=2101-01-02", "report_date_out_of_range"),
    ("period=custom&start=9999-12-31&end=9999-12-31", "report_date_out_of_range"),
    ("&".join("page=1" for _ in range(33)), "invalid_report_request"),
])
@pytest.mark.parametrize("suffix", ["", "/section/tasks", "/section/heatmap", "/export/csv", "/export/pdf"])
def test_rejected_report_inputs_use_400_without_any_dashboard_or_export_work(monkeypatch, suffix, query, code):
    fake_export = Mock(return_value=(b"", "text/csv", "test.csv"))
    handler, fake_report = response(
        "/api/public-reports/monthly/test-token" + suffix + "?" + query,
        monkeypatch,
        export_fn=fake_export,
    )
    assert handler.status == 400
    assert json.loads(handler.wfile.getvalue()) == {"error": code}
    fake_report.assert_not_called()
    fake_export.assert_not_called()


@pytest.mark.parametrize(("query", "expected_page"), [
    ("page=1&period=month", 1),
    ("page=0002&period=month", 2),
    ("page=10000&period=today", 10000),
    ("page=3&period=week", 3),
    ("page=2&period=custom&start=2024-01-01&end=2024-12-31", 2),
    ("page=2&period=custom&start=2026-08-31&end=2026-08-01", 2),
    ("page=1&period=custom&start=2026-08-31&end=2026-08-31", 1),
    ("page=1&period=custom&start=2026-02-28&end=2026-03-01", 1),
])
def test_valid_dashboard_query_preserves_section_and_page(monkeypatch, query, expected_page):
    handler, fake = response(
        "/api/public-reports/monthly/test-token/section/tasks?" + query,
        monkeypatch,
    )
    assert handler.status == 200
    args, _ = fake.call_args
    assert args[:3] == ("test-token", "tasks", expected_page)


@pytest.mark.parametrize("query", [
    "period=month",
    "period=today",
    "period=week",
    "period=custom&start=2024-01-01&end=2024-12-31",
    "period=custom&start=2026-03-30&end=2026-04-03",
])
@pytest.mark.parametrize("format", ["csv", "pdf"])
def test_valid_export_remains_unpaginated_and_passes_period(monkeypatch, query, format):
    fake_export = Mock(return_value=(b"content", "application/octet-stream", "report.test"))
    handler, fake = response(
        "/api/public-reports/monthly/test-token/export/" + format + "?" + query,
        monkeypatch,
        export_fn=fake_export,
    )
    assert handler.status == 200
    assert handler.wfile.getvalue() == b"content"
    assert fake.call_args.kwargs["page_size"] == 0
    assert fake.call_args.kwargs["section"] == "tasks"
    fake_export.assert_called_once()


def test_dashboard_service_validates_before_query_or_heatmap_work(monkeypatch):
    query = Mock(side_effect=AssertionError("invalid request reached SQL"))
    monkeypatch.setattr(dashboard, "_access", lambda token: {"user_id": "42", "bot_key": "default"})
    monkeypatch.setattr(dashboard, "_query_tasks", query)
    with pytest.raises(ValueError, match="report_period_too_large"):
        dashboard.dashboard_report("token", section="heatmap", period="custom",
                                   start_value="2020-01-01", end_value="2026-01-01")
    with pytest.raises(ValueError, match="invalid_report_page"):
        dashboard.dashboard_report("token", section="tasks", page="abc")
    query.assert_not_called()


def test_custom_period_boundaries_include_leap_day_and_reversed_dates():
    assert dashboard.resolve_period("custom", "2024-01-01", "2024-12-31") == (
        date(2024, 1, 1), date(2024, 12, 31)
    )
    assert dashboard.resolve_period("custom", "2026-12-31", "2026-01-01") == (
        date(2026, 1, 1), date(2026, 12, 31)
    )
    with pytest.raises(ValueError, match="report_period_too_large"):
        dashboard.resolve_period("custom", "2024-01-01", "2025-01-01")
    assert len(dashboard._heatmap_data([], date(2024, 1, 1), date(2024, 12, 31))["days"]) == 366


def test_ui_explains_server_boundaries_and_handles_custom_empty_dates():
    script = Path(__file__).resolve().parents[1] / "webapp" / "report_dashboard.js"
    text = script.read_text(encoding="utf-8")
    assert "MAX_CUSTOM_DAYS = 366" in text
    assert "validCustomRange(state.start, state.end)" in text
    assert "report_period_too_large" in text
    assert "invalid_report_page" in text
