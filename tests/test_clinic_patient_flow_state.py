"""Regression tests for interrupted and malformed Clinic patient-registration states (#234)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import clinic as handler


@pytest.fixture
def flow(monkeypatch):
    scope = SimpleNamespace(organization_id="org-1", branch=AsyncMock())
    monkeypatch.setattr(handler, "_scope", AsyncMock(return_value=scope))
    create_patient = AsyncMock(return_value={"id": "patient-1", "display_name": "نیلوفر رضایی"})
    monkeypatch.setattr(handler.service, "create_patient", create_patient)
    menu = AsyncMock()
    monkeypatch.setattr(handler, "clinic_menu", menu)
    message = SimpleNamespace(text=None, reply_text=AsyncMock())
    query = SimpleNamespace(
        answer=AsyncMock(), message=message, edit_message_text=AsyncMock(), data="clinic:new_patient"
    )
    update = SimpleNamespace(
        callback_query=query, effective_message=message,
        effective_user=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(
        user_data={"clinic_organization_id": "org-1", "clinic_branch_id": "unit-1", "other_flow": "keep"},
        application=SimpleNamespace(bot_data={"bot_config": SimpleNamespace(key="clinic")}),
    )
    return SimpleNamespace(
        scope=scope, create_patient=create_patient, menu=menu, message=message,
        query=query, update=update, context=context,
    )


async def start(flow):
    flow.query.data = "clinic:new_patient"
    flow.update.callback_query = flow.query
    await handler.clinic_callback(flow.update, flow.context)


async def enter(flow, value):
    flow.update.callback_query = None
    flow.message.text = value
    return await handler.handle_clinic_input(flow.update, flow.context)


@pytest.mark.asyncio
async def test_full_patient_flow_branch_and_dash_optional_fields(flow):
    await start(flow)
    flow.scope.branch.assert_awaited_once_with("unit-1", "patients.manage")
    assert flow.context.user_data["clinic_input"] == "patient_name"
    for text, next_stage in [
        ("نیلوفر", "patient_family"), ("رضایی", "patient_phone"),
        ("-", "patient_reference"),
    ]:
        assert await enter(flow, text) is True
        assert flow.context.user_data["clinic_input"] == next_stage
    assert await enter(flow, "-") is True
    flow.create_patient.assert_awaited_once()
    args, kwargs = flow.create_patient.await_args
    assert args[1:] == ("unit-1", "نیلوفر رضایی")
    assert kwargs == {"phone": "", "external_reference": None}
    assert flow.context.user_data == {
        "clinic_organization_id": "org-1", "clinic_branch_id": "unit-1", "other_flow": "keep"
    }
    assert await enter(flow, "https://example.com") is False
    flow.create_patient.assert_awaited_once()


@pytest.mark.asyncio
async def test_url_and_unexpected_inputs_do_not_advance_or_create(flow):
    await start(flow)
    for link in ("https://example.org/patient", "www.example.org", "t.me/clinicbot"):
        assert await enter(flow, link) is True
        assert flow.context.user_data["clinic_input"] == "patient_name"
    assert await enter(flow, "آوا") is True
    assert await enter(flow, "محمدی") is True
    assert await enter(flow, "not a phone https://example.org") is True
    assert flow.context.user_data["clinic_input"] == "patient_phone"
    assert await enter(flow, "-") is True
    assert await enter(flow, "https://example.org") is True
    assert flow.context.user_data["clinic_input"] == "patient_reference"
    flow.create_patient.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["clinic_patient_name", "clinic_patient_family", "clinic_patient_phone", "clinic_flow"])
async def test_missing_required_patient_draft_recovers_without_keyerror(flow, missing):
    await start(flow)
    for value in ("آوا", "محمدی", "-"):
        await enter(flow, value)
    flow.context.user_data.pop(missing)
    assert await enter(flow, "1234") is True
    flow.create_patient.assert_not_awaited()
    assert "clinic_input" not in flow.context.user_data
    assert "شروع" in flow.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_unknown_step_and_stale_legacy_patient_stage_are_safe(flow):
    flow.context.user_data["clinic_input"] = "nonsense_step"
    assert await enter(flow, "https://example.org") is True
    assert "clinic_input" not in flow.context.user_data
    flow.context.user_data["clinic_input"] = "patient_reference"
    assert await enter(flow, "https://example.org") is True
    assert "clinic_input" not in flow.context.user_data
    flow.create_patient.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_cancel_menu_and_double_submit_are_safe(flow):
    await start(flow)
    await enter(flow, "آوا")
    assert flow.context.user_data.get("clinic_patient_name") == "آوا"
    await start(flow)  # repeated callback resets the partial draft
    assert "clinic_patient_name" not in flow.context.user_data
    flow.query.data = "clinic:cancel_patient"
    flow.update.callback_query = flow.query
    await handler.clinic_callback(flow.update, flow.context)
    assert "clinic_input" not in flow.context.user_data
    await start(flow)
    flow.query.data = "clinic:menu"
    await handler.clinic_callback(flow.update, flow.context)
    flow.menu.assert_awaited_once()
    assert "clinic_input" not in flow.context.user_data
    await start(flow)
    for value in ("آوا", "محمدی", "-", "-"):
        await enter(flow, value)
    await enter(flow, "-")  # late duplicate text after success is not a new record
    flow.create_patient.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_service_failure_retains_draft_and_retry_succeeds_exactly_once(flow):
    flow.create_patient.side_effect = [RuntimeError("fake-db-outage"), {"id": "patient-1", "display_name": "آوا محمدی"}]
    await start(flow)
    for value in ("آوا", "محمدی", "-", "-"):
        assert await enter(flow, value) is True
    assert flow.context.user_data["clinic_input"] == "patient_reference"
    assert flow.context.user_data["clinic_patient_name"] == "آوا"
    assert flow.context.user_data["clinic_patient_family"] == "محمدی"
    assert flow.create_patient.await_count == 1
    assert await enter(flow, "-") is True
    assert flow.create_patient.await_count == 2
    assert flow.context.user_data.get("clinic_input") is None
    assert await enter(flow, "-") is False
    assert flow.create_patient.await_count == 2


@pytest.mark.asyncio
async def test_change_of_branch_invalidates_patient_draft(flow):
    await start(flow)
    flow.context.user_data["clinic_branch_id"] = "unit-2"
    assert await enter(flow, "آوا") is True
    assert flow.context.user_data.get("clinic_input") is None
    flow.create_patient.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("step,needed", [
    ("followup_title", "clinic_case_id"),
    ("followup_custom_date", "clinic_followup_title"),
    ("typed_session_title", "clinic_patient_id"),
    ("typed_session_custom_date", "clinic_session_title"),
    ("typed_case_title", "clinic_patient_id"),
    ("typed_reschedule", "clinic_reschedule_task_id"),
])
async def test_other_clinic_flows_recover_from_missing_prerequisite(flow, step, needed):
    flow.context.user_data["clinic_input"] = step
    assert await enter(flow, "https://example.org") is True
    assert "clinic_input" not in flow.context.user_data
    assert "مراحل" not in flow.message.reply_text.await_args.args[0] or (
        "دوباره" in flow.message.reply_text.await_args.args[0]
    )
