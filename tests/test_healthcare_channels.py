from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot_platform import BotProfile
from handlers import clinic as telegram_clinic
from services import database
from services.healthcare import csv_io, followups, notifications, reports, service
from services.healthcare.access import ClinicAccessError, Scope
from webapp import clinic_api


@pytest.fixture
def profile(monkeypatch):
    enabled = BotProfile(
        key="clinic",
        name="Clinic",
        username="test_clinic",
        token="synthetic",
        features={"healthcare": True, "clinic_staff_reminders": True},
    )
    monkeypatch.setattr(clinic_api, "get_webapp_bot_profile", lambda key: enabled)
    return enabled


async def test_api_mutations_and_scope_validation(clinic, profile):
    oid = clinic["owner"].organization_id
    query = {"organization_id": [oid]}
    status, response = await clinic_api.dispatch(
        "2", "clinic", "GET", "/api/clinic/patients", query, {}
    )
    assert status == 200 and response["total"] == 1
    with pytest.raises(ClinicAccessError):
        await clinic_api.dispatch(
            "2",
            "clinic",
            "PATCH",
            "/api/clinic/patients/" + clinic["pb"]["id"],
            query,
            {"display_name": "Forbidden"},
        )
    with pytest.raises(ClinicAccessError):
        await clinic_api.dispatch(
            "1",
            "clinic",
            "GET",
            "/api/clinic/patients",
            {"organization_id": ["other"]},
            {},
        )
    status, response = await clinic_api.dispatch(
        "2",
        "clinic",
        "POST",
        "/api/clinic/followups",
        query,
        {
            "case_id": clinic["ca"]["id"],
            "owner_id": "3",
            "due_at": "2026-10-06T10:00:00Z",
        },
    )
    assert status == 201
    fid = response["item"]["id"]
    status, response = await clinic_api.dispatch(
        "2",
        "clinic",
        "POST",
        f"/api/clinic/followups/{fid}/outcome",
        query,
        {"outcome_key": "no_answer", "next_due_at": "2026-10-07T10:00:00Z"},
    )
    assert response["item"]["next_followup_id"]
    with pytest.raises(ClinicAccessError):
        await clinic_api.dispatch(
            "6", "clinic", "GET", f"/api/clinic/followups/{fid}", query, {}
        )


async def test_disabled_profile_denies_clinic_api(clinic, monkeypatch):
    monkeypatch.setattr(
        clinic_api,
        "get_webapp_bot_profile",
        lambda key: BotProfile(
            key="default", name="Default", username="test", token="synthetic"
        ),
    )
    with pytest.raises(ClinicAccessError):
        await clinic_api.dispatch("1", "default", "GET", "/api/clinic/scopes", {}, {})


async def test_telegram_callback_permission_and_idempotent_outcome(clinic, profile):
    f = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "3", "2026-10-06T10:00:00Z"
    )
    query = SimpleNamespace(
        data=f"clinic:retry:{f['id']}:no_answer:1",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=6))
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"bot_config": profile}),
        user_data={"clinic_organization_id": clinic["owner"].organization_id},
    )
    await telegram_clinic.clinic_callback(update, context)
    assert "مجاز نیست" in query.edit_message_text.call_args.args[0]
    assert not (await service.get_entity(clinic["owner"], "followups", f["id"]))[
        "outcome_id"
    ]
    update.effective_user.id = 2
    await telegram_clinic.clinic_callback(update, context)
    await telegram_clinic.clinic_callback(update, context)
    assert (await service.list_entities(clinic["owner"], "followups"))["total"] == 2
    # Runtime feature guard applies even to stale/forged callback payloads.
    context.application.bot_data["bot_config"] = BotProfile(
        key="clinic", name="Disabled", username="test", token="synthetic"
    )
    await telegram_clinic.clinic_callback(update, context)
    assert "مجاز نیست" in query.edit_message_text.call_args.args[0]


async def test_staff_notifications_overlap_cancellation_and_bot_isolation(clinic):
    due = datetime.now(timezone.utc) + timedelta(hours=3)
    f = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "3", due.isoformat()
    )
    bot = SimpleNamespace(send_message=AsyncMock())
    assert (await notifications.deliver(bot, "other", at=due + timedelta(hours=2)))[
        "sent"
    ] == 0
    import asyncio

    await asyncio.gather(
        *[
            notifications.deliver(bot, "clinic", at=due + timedelta(minutes=1))
            for _ in range(4)
        ]
    )
    assert bot.send_message.await_count == 2  # before due and at due, once each
    assert all(c.kwargs["chat_id"] == "3" for c in bot.send_message.call_args_list)
    await followups.record_outcome(clinic["owner"], f["id"], "resolved")
    await notifications.deliver(bot, "clinic", at=due + timedelta(days=2))
    assert bot.send_message.await_count == 2
    events = await database.fetch_all_sql(
        "SELECT * FROM operational_audit WHERE action='notification.sent'"
    )
    assert len(events) == 2


async def test_notification_failure_and_revocation_are_safe(clinic):
    due = datetime.now(timezone.utc) - timedelta(days=2)
    f = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "3", due.isoformat()
    )
    bot = SimpleNamespace(
        send_message=AsyncMock(side_effect=TimeoutError("synthetic failure"))
    )
    result = await notifications.deliver(bot, "clinic")
    assert result["failed"] == 1
    await notifications.deliver(bot, "clinic")
    assert bot.send_message.await_count == 1  # ambiguous delivery is not retried
    other = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "2", due.isoformat()
    )
    await service.set_membership(
        clinic["owner"], "2", "reception", clinic["a"], active=False
    )
    assert (await notifications.deliver(bot, "clinic"))["cancelled"] == 1
    assert (await service.get_entity(clinic["owner"], "followups", f["id"]))[
        "status"
    ] == "due"
    assert other["owner_user_id"] == "2"


async def test_case_close_cancels_pending_tasks_and_notifications(clinic):
    due = datetime.now(timezone.utc) + timedelta(hours=3)
    f = await followups.create_followup(
        clinic["owner"], clinic["ca"]["id"], "3", due.isoformat()
    )
    await service.set_case_status(clinic["owner"], clinic["ca"]["id"], "closed")
    assert (await service.get_entity(clinic["owner"], "tasks", f["task_id"]))[
        "status"
    ] == "cancelled"
    assert (await service.get_entity(clinic["owner"], "followups", f["id"]))[
        "status"
    ] == "closed"
    rows = await database.fetch_all_sql(
        "SELECT status FROM operational_notifications WHERE task_id=?", (f["task_id"],)
    )
    assert rows and all(r["status"] == "cancelled" for r in rows)


async def test_csv_preview_idempotency_permissions_and_minimization(clinic):
    scope = Scope(clinic["owner"].organization_id, "2")
    content = f"external_id,display_name,phone,branch_id\nNEW1,Synthetic Import,,{clinic['a']}\n"
    assert (await csv_io.preview_patients(scope, content))["valid"] == 1
    assert await csv_io.import_patients(scope, content, confirmed=True) == {
        "imported": 1,
        "duplicates": 0,
    }
    assert await csv_io.import_patients(scope, content, confirmed=True) == {
        "imported": 0,
        "duplicates": 1,
    }
    invalid = content.replace(clinic["a"], clinic["b"])
    assert (await csv_io.preview_patients(scope, invalid))["invalid"] == 1
    with pytest.raises(ValueError):
        await csv_io.import_patients(scope, invalid, confirmed=True)
    with pytest.raises(ValueError):
        await csv_io.preview_patients(scope, content.replace("phone", "diagnosis"))
    with pytest.raises(ClinicAccessError):
        await csv_io.export_operations(scope, "cases")
    exported = await csv_io.export_operations(
        clinic["owner"], "cases", branch_id=clinic["a"]
    )
    assert exported["rows"] == 1
    assert "phone" not in exported["csv"] and "display_name" not in exported["csv"]
    assert "Synthetic A" not in exported["csv"]


async def test_metrics_branch_scope_and_facts(clinic):
    scope = clinic["owner"]
    f = await followups.create_followup(
        scope, clinic["ca"]["id"], "3", "2026-10-06T10:00:00Z"
    )
    await followups.record_outcome(scope, f["id"], "resolved")
    await followups.create_followup(
        scope, clinic["cb"]["id"], "6", "2026-10-06T10:00:00Z"
    )
    await service.set_membership(scope, "10", "manager", clinic["a"])
    m = await reports.metrics(Scope(scope.organization_id, "10"))
    assert m["tasks"]["total"] == 1 and m["followups"]["completion_rate"] == 1
    assert m["cases"]["missing_next_action"] == 1
    assert m["followups"]["median_delay_seconds"] >= 0
    with pytest.raises(ClinicAccessError):
        await reports.metrics(Scope(scope.organization_id, "2"))
    assert (
        await reports.metrics(Scope(scope.organization_id, "10"), branch_id=clinic["b"])
    )["tasks"]["total"] == 0


async def test_manager_can_close_after_creator_or_owner_is_deactivated(clinic):
    scope = clinic["owner"]
    reception = Scope(scope.organization_id, "2")
    f = await followups.create_followup(
        reception, clinic["ca"]["id"], "3", "2026-10-07T10:00:00Z"
    )
    await service.set_membership(scope, "2", "reception", clinic["a"], active=False)
    await service.set_membership(scope, "3", "coordinator", clinic["a"], active=False)
    await service.set_case_status(scope, clinic["ca"]["id"], "closed")
    assert (await service.get_entity(scope, "tasks", f["task_id"]))[
        "status"
    ] == "cancelled"
