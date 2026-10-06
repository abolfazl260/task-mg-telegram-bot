from __future__ import annotations

import http.client
import io
import json
import threading

from webapp import report_routes
from webapp.server import ThreadingHTTPServer, WebAppHandler


class _FakeHandler:
    def __init__(self, path: str):
        self.path = path
        self.command = "GET"
        self.headers = {}
        self.status = None
        self.response_headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        return None


def _response_json(handler: _FakeHandler) -> dict:
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


def test_report_generation_500_does_not_expose_exception_text(monkeypatch):
    secret = "db-password=super-secret"

    def fail_report(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(report_routes, "dashboard_report", fail_report)
    handler = _FakeHandler(
        "/api/public-reports/monthly/test-token/section/tasks?period=month"
    )

    assert report_routes.handle_report_api(handler) is True
    assert handler.status == 500
    assert _response_json(handler) == {"error": "report_generation_failed"}
    assert secret.encode() not in handler.wfile.getvalue()
    assert b"detail" not in handler.wfile.getvalue()


def test_report_export_requests_complete_filtered_task_rows(monkeypatch):
    captured = {}

    def fake_dashboard_report(token, **kwargs):
        captured["token"] = token
        captured.update(kwargs)
        return {
            "summary": {"total": 2},
            "rows": [
                {"id": "1", "title": "A"},
                {"id": "2", "title": "B"},
            ],
        }

    def fake_export(report, fmt):
        captured["report"] = report
        captured["fmt"] = fmt
        return b"csv-data", "text/csv; charset=utf-8", "report.csv"

    monkeypatch.setattr(report_routes, "dashboard_report", fake_dashboard_report)
    monkeypatch.setattr(report_routes, "export_report", fake_export)

    handler = _FakeHandler(
        '/api/public-reports/monthly/test-token/export/csv?period=custom&start=2026-08-01&end=2026-08-31&search=%7B%22priority%22%3A%22high%22%7D'
    )

    assert report_routes.handle_report_api(handler) is True
    assert handler.status == 200
    assert handler.wfile.getvalue() == b"csv-data"
    assert captured["token"] == "test-token"
    assert captured["section"] == "tasks"
    assert captured["page"] == 1
    assert captured["page_size"] == 0
    assert captured["period"] == "custom"
    assert captured["start_value"] == "2026-08-01"
    assert captured["end_value"] == "2026-08-31"
    assert captured["search"] == '{"priority":"high"}'
    assert len(captured["report"]["rows"]) == 2
    assert captured["fmt"] == "csv"


def test_report_export_500_does_not_expose_exception_text(monkeypatch):
    secret = "/srv/private/report-template.pdf"

    monkeypatch.setattr(
        report_routes,
        "dashboard_report",
        lambda *args, **kwargs: {"summary": {}, "rows": []},
    )

    def fail_export(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(report_routes, "export_report", fail_export)
    handler = _FakeHandler(
        "/api/public-reports/monthly/test-token/export/pdf?period=month"
    )

    assert report_routes.handle_report_api(handler) is True
    assert handler.status == 500
    assert _response_json(handler) == {"error": "report_export_failed"}
    assert secret.encode() not in handler.wfile.getvalue()
    assert b"detail" not in handler.wfile.getvalue()


def test_generic_webapp_500_does_not_expose_exception_text(monkeypatch):
    secret = "internal-schema-name users_private"

    def fail_api(self, method):
        raise RuntimeError(secret)

    monkeypatch.setattr(WebAppHandler, "_handle_api", fail_api)
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_port, timeout=2
        )
        connection.request("GET", "/api/me")
        response = connection.getresponse()
        body = response.read()
        connection.close()

        assert response.status == 500
        assert json.loads(body) == {"error": "internal_server_error"}
        assert secret.encode() not in body
        assert b"detail" not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
