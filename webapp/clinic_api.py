"""Authenticated clinic API; the same Scope service protects Telegram callbacks."""

from __future__ import annotations

from services import (
    attachment_service,
    clinic_dashboard,
    clinic_setup,
    clinic_typed,
    clinic_typed_io,
    contact_point_service,
    report_definition_service,
)
from services.database import fetch_all_sql, fetch_one_sql
from services.healthcare import csv_io, followups, reports, service, workflows
from services.healthcare.access import ClinicAccessError, Scope, actor_scopes
from services.work_item_access import authorized_task
from webapp.bot_profile import get_webapp_bot_profile


async def dispatch(actor_id, bot_key, method, path, query, data):
    profile = get_webapp_bot_profile(bot_key)
    if not profile.feature_enabled("healthcare"):
        raise ClinicAccessError("forbidden")
    if path == "/api/clinic/scopes" and method == "GET":
        return 200, {"items": await actor_scopes(str(actor_id), profile.key)}
    # Keep the workspace id available for shared Core endpoints below.
    oid = (query.get("organization_id") or [""])[0]
    if path == "/api/clinic/organizations" and method == "POST":
        oid = await service.create_organization(
            str(actor_id), profile.key, data.get("name"), data.get("timezone", "Asia/Tehran")
        )
        return 201, {"organization_id": oid}
    if path == "/api/clinic/setup" and method == "POST":
        return 200, await clinic_setup.bootstrap_async(
            str(actor_id), profile.key, data.get("name"), timezone_name=data.get("timezone", "Asia/Tehran"),
            branches=data.get("branches"), staff=data.get("staff"), field_config=data.get("field_config"),
        )
    if not oid or not await fetch_one_sql(
        "SELECT 1 FROM workspaces WHERE id=? AND bot_key=?", (oid, profile.key)
    ):
        raise ClinicAccessError("forbidden")
    scope = Scope(oid, str(actor_id))
    if path == "/api/clinic/setup/status" and method == "GET":
        return 200, await clinic_setup.setup_status_async(oid, str(actor_id))
    if path == "/api/clinic/typed/import/preview" and method == "POST":
        return 200, await clinic_typed_io.preview_async(scope, data.get("csv"), branch_id=data.get("branch_id"))
    if path == "/api/clinic/typed/import/confirm" and method == "POST":
        return 200, await clinic_typed_io.import_async(scope, data.get("csv"), branch_id=data.get("branch_id"), confirmed=data.get("confirmed") is True)
    if path == "/api/clinic/typed/export" and method == "GET":
        return 200, await clinic_typed_io.export_async(scope, str(actor_id), branch_id=(query.get("branch_id") or [None])[0])
    if path == "/api/clinic/dashboard" and method == "GET":
        await scope.predicate("reports.view")
        return 200, await clinic_dashboard.dashboard_async(oid, str(actor_id), branch_id=(query.get("branch_id") or [None])[0])
    if path == "/api/clinic/navigation" and method == "GET":
        terminology = profile.settings.get("terminology", {})
        candidates = [
            ("patients", "/clinic/patients", "patients.view", terminology.get("patient", "بیماران")),
            ("sessions", "/clinic/sessions", "tasks.view", "جلسات"),
            ("followups", "/clinic/followups", "followups.view", terminology.get("followup", "پیگیری‌ها")),
            ("doctors", "/clinic/staff", "memberships.manage", "کادر درمان"),
            ("reports", "/clinic/reports", "reports.view", "گزارش‌ها"),
        ]
        items = []
        for key, route, permission, label in candidates:
            try:
                await scope.predicate(permission)
            except PermissionError:
                continue
            items.append({"key": key, "route": route, "label": label})
        return 200, {"vertical": "clinic", "title": terminology.get("workspace", profile.name), "items": items, "branding": profile.settings.get("branding", {})}
    # Typed Clinic hierarchy: Patient roots with Session/Follow-up children.
    if path == "/api/clinic/typed/patients" and method == "GET":
        from services.work_item_access import workspace_predicate
        pred, args = await workspace_predicate(oid, str(actor_id), alias="t", action="view")
        filters = [pred, "t.work_item_type='patient'", "t.archived_at IS NULL"]
        params = list(args)
        search = (query.get("search") or [""])[0].strip()
        if search:
            filters.append("(LOWER(t.title) LIKE ? OR EXISTS (SELECT 1 FROM task_contact_points cp WHERE cp.task_id=t.id AND cp.status='active' AND cp.normalized_value LIKE ?))")
            params.extend([f"%{search.lower()}%", f"%{search.casefold()}%"])
        if (query.get("branch_id") or [None])[0]: filters.append("t.unit_id=?"); params.append((query.get("branch_id") or [None])[0])
        if (query.get("doctor_id") or [None])[0]: filters.append("t.assignee_id=?"); params.append((query.get("doctor_id") or [None])[0])
        limit, offset = max(1, min(int((query.get("limit") or ["25"])[0]), 100)), max(0, int((query.get("offset") or ["0"])[0]))
        where = " AND ".join(filters)
        total = await fetch_one_sql("SELECT COUNT(*) AS n FROM tasks t WHERE " + where, tuple(params))
        rows = await fetch_all_sql(
            """SELECT t.*,d.data_json,
                      COALESCE((
                          SELECT cp.value
                          FROM task_contact_points cp
                          WHERE cp.task_id=t.id AND cp.status='active' AND cp.type='phone'
                          ORDER BY cp.is_primary DESC,cp.created_at,cp.id
                          LIMIT 1
                      ),'') AS primary_phone
               FROM tasks t
               LEFT JOIN typed_work_item_data d ON d.task_id=t.id
               WHERE """ + where + " ORDER BY t.created_at DESC,t.id LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )
        for row in rows:
            row["typed"] = clinic_typed._parse(row.pop("data_json", "{}"))
        return 200, {"items": rows, "total": int((total or {}).get("n") or 0), "limit": limit, "offset": offset}
    if path == "/api/clinic/typed/patients" and method == "POST":
        return 201, {"item": await clinic_typed.create_patient_async(
            scope, data.get("branch_id"), data.get("display_name"),
            doctor_id=data.get("doctor_id"), reference_id=data.get("reference_id"),
        )}
    if path == "/api/clinic/typed/sessions" and method == "GET":
        from services.work_item_access import workspace_predicate
        pred, args = await workspace_predicate(oid, str(actor_id), alias="t", action="view")
        filters = [pred, "t.work_item_type='session'", "t.archived_at IS NULL"]
        params = list(args)
        search = (query.get("search") or [""])[0].strip()
        if search:
            filters.append("(LOWER(t.title) LIKE ? OR LOWER(COALESCE(p.title,'')) LIKE ?)")
            needle = f"%{search.lower()}%"
            params.extend([needle, needle])
        branch_id = (query.get("branch_id") or [None])[0]
        doctor_id = (query.get("doctor_id") or [None])[0]
        status = (query.get("status") or [None])[0]
        if branch_id:
            filters.append("t.unit_id=?")
            params.append(branch_id)
        if doctor_id:
            filters.append("t.assignee_id=?")
            params.append(doctor_id)
        if status:
            filters.append("t.status=?")
            params.append(status)
        limit = max(1, min(int((query.get("limit") or ["50"])[0]), 100))
        offset = max(0, int((query.get("offset") or ["0"])[0]))
        where = " AND ".join(filters)
        total = await fetch_one_sql(
            "SELECT COUNT(*) AS n FROM tasks t LEFT JOIN tasks p ON p.id=t.parent_task_id WHERE " + where,
            tuple(params),
        )
        rows = await fetch_all_sql(
            """SELECT t.*,p.title AS patient_name,d.data_json
               FROM tasks t
               LEFT JOIN tasks p ON p.id=t.parent_task_id
               LEFT JOIN typed_work_item_data d ON d.task_id=t.id
               WHERE """ + where + """
               ORDER BY CASE WHEN COALESCE(t.deadline,'')='' THEN 1 ELSE 0 END,
                        t.deadline,t.created_at,t.id
               LIMIT ? OFFSET ?""",
            tuple(params) + (limit, offset),
        )
        for row in rows:
            row["typed"] = clinic_typed._parse(row.pop("data_json", "{}"))
        return 200, {"items": rows, "total": int((total or {}).get("n") or 0), "limit": limit, "offset": offset}
    if path == "/api/clinic/typed/contact-points" and method == "GET":
        return 200, {"items": await contact_point_service.list_contact_points_async(
            (query.get("task_id") or [""])[0], str(actor_id), include_inactive=(query.get("include_inactive") or ["false"])[0] == "true"
        )}
    if path == "/api/clinic/typed/contact-points" and method == "POST":
        return 201, {"item": await contact_point_service.create_contact_point_async(
            data.get("task_id"), data.get("type"), data.get("value"), str(actor_id),
            label=data.get("label", ""), is_primary=bool(data.get("is_primary", False)), note=data.get("note", ""), status=data.get("status", "active")
        )}
    if path.startswith("/api/clinic/typed/contact-points/") and method == "PATCH":
        point_id = path.rsplit("/", 1)[-1]
        return 200, {"item": await contact_point_service.update_contact_point_async(
            point_id, str(actor_id), value=data.get("value"), label=data.get("label"), is_primary=data.get("is_primary"), note=data.get("note"), status=data.get("status")
        )}
    if path == "/api/clinic/typed/children" and method == "GET":
        return 200, await clinic_typed.list_children_async(
            (query.get("parent_task_id") or [""])[0], str(actor_id),
            item_type=(query.get("item_type") or [None])[0], status=(query.get("status") or [None])[0],
            limit=int((query.get("limit") or ["50"])[0]), offset=int((query.get("offset") or ["0"])[0]),
        )
    if path == "/api/clinic/typed/children" and method == "POST":
        return 201, {"item": await clinic_typed.create_child_async(
            scope, data.get("parent_task_id"), data.get("item_type", "session"), data.get("title"),
            scheduled_at=data.get("scheduled_at"), doctor_id=data.get("doctor_id"), branch_id=data.get("branch_id"), fields=data.get("fields"),
        )}
    if path.startswith("/api/clinic/typed/items/") and method in {"GET", "PATCH"}:
        item_id = path.rsplit("/", 1)[-1]
        if method == "GET":
            item = await clinic_typed._item(item_id, str(actor_id))
            children = await clinic_typed.list_children_async(item_id, str(actor_id)) if item.get("work_item_type") == "patient" else {"items": [], "total": 0}
            contacts = await contact_point_service.list_contact_points_async(item_id, str(actor_id), include_inactive=True)
            files = await attachment_service.list_attachments_async(item_id, str(actor_id), include_archived=False)
            return 200, {"item": item, "children": children, "contact_points": contacts, "attachments": files, "tabs": ["profile", "contact", "medical_history", "medications", "allergies", "diagnoses", "clinical_notes", "sessions", "followups", "files", "activity"]}
        return 200, {"item": await clinic_typed.update_item_async(item_id, str(actor_id), title=data.get("title"), fields=data.get("fields"))}
    if path.startswith("/api/clinic/typed/items/") and path.endswith("/assign") and method == "POST":
        item_id = path.split("/")[-2]
        return 200, {"item": await clinic_typed.assign_async(item_id, str(actor_id), data.get("user_id"))}
    if path.startswith("/api/clinic/typed/items/") and path.endswith("/status") and method == "PATCH":
        item_id = path.split("/")[-2]
        return 200, {"item": await clinic_typed.transition_async(item_id, str(actor_id), data.get("status"), fields=data.get("fields"))}
    if path.startswith("/api/clinic/typed/sessions/") and path.endswith("/reschedule") and method == "POST":
        item_id = path.split("/")[-2]
        return 200, {"item": await clinic_typed.reschedule_async(item_id, str(actor_id), data.get("scheduled_at"))}
    # Core attachment/report endpoints are shared by every enabled Vertical.
    # Scope is checked before delegating to the generic services.
    if path == "/api/clinic/attachments" and method == "GET":
        task_id = (query.get("task_id") or [""])[0]
        if not task_id:
            raise ValueError("task_id_required")
        await authorized_task(task_id, str(actor_id), workspace_id=oid)
        return 200, {"items": await attachment_service.list_attachments_async(
            task_id, str(actor_id), attribute_definition_id=(query.get("attribute_definition_id") or [None])[0],
            include_archived=(query.get("include_archived") or ["false"])[0].lower() == "true",
            limit=int((query.get("limit") or ["100"])[0]), offset=int((query.get("offset") or ["0"])[0]),
        )}
    if path == "/api/clinic/attachments" and method == "POST":
        await authorized_task(data.get("task_id"), str(actor_id), write=True, workspace_id=oid)
        return 201, {"item": await attachment_service.attach_file_async(
            data.get("task_id"), str(actor_id), file_id=data.get("file_id"),
            filename=data.get("filename", ""), media_type=data.get("media_type", "application/octet-stream"),
            size_bytes=data.get("size_bytes", 0), storage_key=data.get("storage_key", ""),
            attribute_definition_id=data.get("attribute_definition_id"), attribute_ordinal=data.get("attribute_ordinal", 0),
            metadata=data.get("metadata"),
        )}
    if path.startswith("/api/clinic/attachments/") and path.endswith("/archive") and method == "POST":
        attachment_id = path.split("/")[-2]
        item = await attachment_service.get_attachment_async(attachment_id, str(actor_id), include_archived=True)
        if not item or item.get('workspace_id') != oid:
            raise ClinicAccessError('forbidden')
        return 200, {"archived": await attachment_service.archive_attachment_async(attachment_id, str(actor_id))}
    if path == "/api/clinic/reports/definitions" and method == "GET":
        await scope.predicate("reports.view")
        return 200, {"items": await report_definition_service.list_report_definitions_async(
            actor_id=str(actor_id), workspace_id=oid, bot_key=profile.key,
            source_item_type=(query.get("source_item_type") or [None])[0],
        )}
    if path == "/api/clinic/reports/definitions" and method == "POST":
        await scope.predicate("reports.view")
        definition = await report_definition_service.create_report_definition_async(
            name=data.get("name"), title=data.get("title"), source_item_type=data.get("source_item_type", "task"),
            created_by=str(actor_id), workspace_id=oid, bot_key=profile.key, filters=data.get("filters"),
            group_by=data.get("group_by", ""), date_field=data.get("date_field", "created_at"),
            metric=data.get("metric", "count"), label=data.get("label", ""),
            role_permissions=data.get("role_permissions"), branch_scope=data.get("branch_scope", "any"),
            drill_down=data.get("drill_down"),
        )
        return 201, {"item": definition}
    if path.startswith("/api/clinic/reports/") and method == "GET":
        await scope.predicate("reports.view")
        report_id = path.rsplit("/", 1)[-1]
        return 200, await report_definition_service.execute_report_async(
            report_id, str(actor_id), from_date=(query.get("from_date") or [None])[0],
            to_date=(query.get("to_date") or [None])[0], page=int((query.get("page") or ["1"])[0]),
            page_size=int((query.get("page_size") or ["50"])[0]),
        )
    if path == "/api/clinic/branches":
        if method == "GET":
            pred, args = await scope.predicate(
                "cases.view", "b", doctor_context="?=?", branch_column="id"
            )
            return 200, {
                "items": await fetch_all_sql(
                    f"SELECT b.* FROM workspace_units b WHERE {pred} ORDER BY b.name",  # nosec B608
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
    if path == "/api/clinic/report" and method == "GET":
        return 200, await service.clinic_report(scope, unit_id=(query.get("branch_id") or [None])[0])
    if path == "/api/clinic/metrics" and method == "GET":
        return 200, await reports.metrics(
            scope, unit_id=(query.get("branch_id") or [None])[0]
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
            unit_id=(query.get("branch_id") or [None])[0],
        )
    if path.startswith("/api/clinic/clinical-records/"):
        patient_id = path.rsplit("/", 1)[-1]
        if method == "GET": return 200, {"item": await service.get_clinical_record(scope, patient_id)}
        if method in {"POST", "PATCH"}: return 200, {"item": await service.save_clinical_record(scope, patient_id, data)}
    parts = path.removeprefix("/api/clinic/").split("/")
    kind = parts[0]
    if kind not in service.TABLES:
        return 404, {"error": "not_found"}
    if len(parts) == 1 and method == "GET":
        filter_map = {
            "branch_id": "unit_id",
            "owner_id": "owner_id",
            "doctor_id": "doctor_id",
            "status": "status",
            "stage": "stage",
            "search": "search",
            "limit": "limit",
            "offset": "offset",
        }
        filters = {
            internal: (query[external] or [""])[0]
            for external, internal in filter_map.items()
            if external in query
        }
        if kind == "followups" and "view" in query:
            filters = {
                key: value
                for key, value in filters.items()
                if key in {"unit_id", "owner_id", "doctor_id", "limit", "offset"}
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
                external_reference=data.get("appointment_reference", ""),
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
