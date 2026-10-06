"""Authenticated clinic API; the same Scope service protects Telegram callbacks."""

from __future__ import annotations

from services.database import fetch_all_sql, fetch_one_sql
from services.healthcare import csv_io, followups, reports, service, workflows
from services.healthcare.access import ClinicAccessError, Scope, actor_scopes
from webapp.bot_profile import get_webapp_bot_profile


async def dispatch(actor_id, bot_key, method, path, query, data):
    profile = get_webapp_bot_profile(bot_key)
    if not profile.feature_enabled("healthcare"):
        raise ClinicAccessError("forbidden")
    if path == "/api/clinic/scopes" and method == "GET":
        return 200, {"items": await actor_scopes(str(actor_id), profile.key)}
    if path == "/api/clinic/organizations" and method == "POST":
        oid = await service.create_organization(
            str(actor_id),
            profile.key,
            data.get("name"),
            data.get("timezone", "Asia/Tehran"),
        )
        return 201, {"organization_id": oid}
    oid = (query.get("organization_id") or [""])[0]
    if not oid or not await fetch_one_sql(
        "SELECT 1 FROM clinic_organizations WHERE id=? AND bot_key=?",
        (oid, profile.key),
    ):
        raise ClinicAccessError("forbidden")
    scope = Scope(oid, str(actor_id))
    if path == "/api/clinic/branches":
        if method == "GET":
            pred, args = await scope.predicate(
                "cases.view", "b", doctor_context="?=?", branch_column="id"
            )
            return 200, {
                "items": await fetch_all_sql(
                    f"SELECT b.* FROM clinic_branches b WHERE {pred} ORDER BY b.name",  # nosec B608
                    args,
                )
            }  # nosec B608
        if method == "POST":
            return 201, {
                "branch_id": await service.create_branch(scope, data.get("name"))
            }
    if path == "/api/clinic/memberships" and method == "POST":
        if not isinstance(data.get("active", True), bool):
            raise ValueError("invalid_active")
        return 200, {
            "membership_id": await service.set_membership(
                scope,
                service.text(data.get("user_id"), max_length=100),
                data.get("role"),
                data.get("branch_id"),
                data.get("active", True),
            )
        }
    if path == "/api/clinic/templates":
        if method == "GET":
            return 200, {"items": await workflows.list_templates(scope)}
        if method == "POST":
            return 201, {
                "item": await workflows.publish(
                    scope, data.get("template_key"), data.get("definition")
                )
            }
    if path == "/api/clinic/templates/seed" and method == "POST":
        return 200, {"items": await workflows.seed_defaults(scope)}
    if path == "/api/clinic/metrics" and method == "GET":
        return 200, await reports.metrics(
            scope, branch_id=(query.get("branch_id") or [None])[0]
        )
    if path == "/api/clinic/import/preview" and method == "POST":
        return 200, await csv_io.preview_patients(scope, data.get("csv"))
    if path == "/api/clinic/import/confirm" and method == "POST":
        return 200, await csv_io.import_patients(
            scope, data.get("csv"), confirmed=data.get("confirmed")
        )
    if path == "/api/clinic/export" and method == "GET":
        return 200, await csv_io.export_operations(
            scope,
            (query.get("kind") or ["tasks"])[0],
            branch_id=(query.get("branch_id") or [None])[0],
        )
    parts = path.removeprefix("/api/clinic/").split("/")
    kind = parts[0]
    if kind not in service.TABLES:
        return 404, {"error": "not_found"}
    if len(parts) == 1 and method == "GET":
        filters = {
            key: (query[key] or [""])[0]
            for key in (
                "branch_id",
                "owner_id",
                "doctor_id",
                "status",
                "stage",
                "search",
                "limit",
                "offset",
            )
            if key in query
        }
        if kind == "followups" and "view" in query:
            filters = {
                key: value
                for key, value in filters.items()
                if key in {"branch_id", "owner_id", "doctor_id", "limit", "offset"}
            }
            return 200, await followups.queue(
                scope, (query["view"] or ["today"])[0], **filters
            )
        if kind == "cases":
            filters["missing_next_action"] = (
                query.get("missing_next_action") or ["false"]
            )[0] == "true"
        return 200, await service.list_entities(scope, kind, **filters)
    if len(parts) == 1 and method == "POST":
        if kind == "patients":
            item = await service.create_patient(
                scope,
                data.get("branch_id"),
                data.get("display_name"),
                external_reference=data.get("external_reference"),
                phone=data.get("phone", ""),
                doctor_id=data.get("doctor_id"),
            )
        elif kind == "cases":
            item = await service.create_case(
                scope,
                data.get("patient_id"),
                data.get("title"),
                data.get("owner_id"),
                case_type=data.get("case_type", "callback"),
                doctor_id=data.get("doctor_id"),
                expected_at=data.get("expected_at"),
                appointment_reference=data.get("appointment_reference", ""),
            )
        elif kind == "tasks":
            item = await service.create_action(
                scope,
                data.get("case_id"),
                data.get("title"),
                data.get("owner_id"),
                data.get("due_at"),
            )
        else:
            item = await followups.create_followup(
                scope,
                data.get("case_id"),
                data.get("owner_id"),
                data.get("due_at"),
                title=data.get("title", "پیگیری بیمار"),
                followup_type=data.get("followup_type", "callback"),
            )
        return 201, {"item": item}
    if len(parts) == 2:
        if method == "GET":
            return 200, {"item": await service.get_entity(scope, kind, parts[1])}
        if method == "PATCH" and kind == "patients":
            return 200, {
                "item": await service.update_patient(
                    scope,
                    parts[1],
                    display_name=data.get("display_name"),
                    phone=data.get("phone"),
                    doctor_id=data.get("doctor_id"),
                    archive=data.get("archive") is True,
                )
            }
        if method == "PATCH" and kind == "cases":
            return 200, {
                "item": await service.set_case_status(
                    scope, parts[1], data.get("status"), blocker=data.get("blocker", "")
                )
            }
        if method == "PATCH" and kind == "tasks":
            return 200, {
                "item": await service.set_task_status(
                    scope, parts[1], data.get("status")
                )
            }
    if len(parts) == 3:
        entity_id, operation = parts[1:]
        if kind == "tasks" and operation == "outcome" and method == "POST":
            return 200, {
                "item": await service.record_task_outcome(
                    scope,
                    entity_id,
                    data.get("outcome_key"),
                    next_task_id=data.get("next_task_id"),
                )
            }
        if kind == "followups" and operation == "outcome" and method == "POST":
            return 200, {
                "item": await followups.record_outcome(
                    scope,
                    entity_id,
                    data.get("outcome_key"),
                    next_due_at=data.get("next_due_at"),
                    next_owner_id=data.get("next_owner_id"),
                )
            }
        if kind == "cases":
            if operation == "timeline" and method == "GET":
                return 200, await service.timeline(scope, entity_id)
            if operation == "workflow" and method == "POST":
                return 201, {
                    "item": await workflows.start(
                        scope, entity_id, data.get("version_id"), data.get("owner_id")
                    )
                }
            if operation == "stage" and method == "POST":
                return 200, {
                    "item": await workflows.transition(
                        scope,
                        entity_id,
                        data.get("target_stage"),
                        data.get("owner_id"),
                        expected_stage=data.get("expected_stage"),
                    )
                }
    return 405, {"error": "method_not_allowed"}
