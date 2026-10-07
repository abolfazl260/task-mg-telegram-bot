from __future__ import annotations

import threading
import urllib.request

import pytest

from bot_platform import BotProfile
from services import clinic_typed, contact_point_service
from webapp import clinic_api
from webapp.server import ThreadingHTTPServer, WebAppHandler


def _start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.parametrize("path", ["/clinic", "/clinic/patients", "/clinic/sessions", "/clinic/patients/example-id"])
def test_clinic_workspace_routes_serve_dedicated_shell(path):
    server, thread = _start_server()
    try:
        with urllib.request.urlopen(  # nosec B310 -- loopback HTTP test server only
            f"http://127.0.0.1:{server.server_port}{path}", timeout=2
        ) as response:
            html = response.read().decode("utf-8")
        assert response.status == 200
        assert "فضای کار کلینیک" in html
        assert 'data-auth-protected hidden' in html
        assert '/static/clinic.js' in html
        assert '/static/auth-guard.js' in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def clinic_profile(monkeypatch):
    enabled = BotProfile(
        key="clinic",
        name="Clinic",
        username="test_clinic",
        token="synthetic",
        features={"healthcare": True, "tasks": True},
    )
    monkeypatch.setattr(clinic_api, "get_webapp_bot_profile", lambda _key: enabled)
    return enabled


@pytest.mark.asyncio
async def test_typed_patient_list_exposes_typed_fields_and_primary_phone(clinic, clinic_profile):
    patient = await clinic_typed.create_patient_async(
        clinic["owner"], clinic["a"], "Web Patient", patient_id="WEB-001"
    )
    assert patient["reference_id"] is None
    await clinic_typed.update_item_async(
        patient["id"], "1", fields={"first_name": "Web", "status": "active"}
    )
    await contact_point_service.create_contact_point_async(
        patient["id"], "phone", "+989121234567", "1",
        label="mobile", is_primary=True,
    )

    status, payload = await clinic_api.dispatch(
        "2",
        "clinic",
        "GET",
        "/api/clinic/typed/patients",
        {
            "organization_id": [clinic["owner"].organization_id],
            "search": ["Web Patient"],
        },
        {},
    )

    assert status == 200
    row = next(item for item in payload["items"] if item["id"] == patient["id"])
    assert row["typed"]["first_name"] == "Web"
    assert row["typed"]["patient_id"] == "WEB-001"
    assert row["primary_phone"] == "+989121234567"


@pytest.mark.asyncio
async def test_session_list_is_filterable_and_branch_scoped(clinic, clinic_profile):
    patient_a = await clinic_typed.create_patient_async(
        clinic["owner"], clinic["a"], "Patient A"
    )
    patient_b = await clinic_typed.create_patient_async(
        clinic["owner"], clinic["b"], "Patient B"
    )
    session_a = await clinic_typed.create_child_async(
        clinic["owner"],
        patient_a["id"],
        "session",
        "Consultation A",
        scheduled_at="2026-10-10T10:00:00+03:30",
        fields={"session_type": "consultation"},
    )
    await clinic_typed.create_child_async(
        clinic["owner"],
        patient_b["id"],
        "session",
        "Consultation B",
        scheduled_at="2026-10-10T12:00:00+03:30",
        fields={"session_type": "consultation"},
    )

    status, payload = await clinic_api.dispatch(
        "2",
        "clinic",
        "GET",
        "/api/clinic/typed/sessions",
        {
            "organization_id": [clinic["owner"].organization_id],
            "status": ["scheduled"],
        },
        {},
    )

    assert status == 200
    assert [row["id"] for row in payload["items"]] == [session_a["id"]]
    assert payload["items"][0]["patient_name"] == "Patient A"
    assert payload["items"][0]["typed"]["session_type"] == "consultation"
