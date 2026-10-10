"""Minimal role-scoped clinic execution menu using the shared domain service."""

from __future__ import annotations  # noqa: I001 - preserve established import grouping

import logging
import re
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services import clinic_typed
from services.conversation_state import clear_flow, has_step, start_flow
from services.date_picker import deadline_label, deadline_value
from services.healthcare import followups, reports, service
from services.healthcare.access import ClinicAccessError, Scope, actor_scopes
from services.operations.service import create_workspace
from services.permission_service import is_admin


logger = logging.getLogger(__name__)
_PATIENT_FLOW = "patient_registration"
_PATIENT_DRAFT_KEYS = (
    "clinic_patient_name", "clinic_patient_family", "clinic_patient_phone",
    "clinic_patient_org_id", "clinic_patient_branch_id",
    "clinic_patient_submitting",
)
_PATIENT_STEPS = {
    "patient_name": ("clinic_patient_org_id", "clinic_patient_branch_id"),
    "patient_family": ("clinic_patient_org_id", "clinic_patient_branch_id", "clinic_patient_name"),
    "patient_phone": ("clinic_patient_org_id", "clinic_patient_branch_id", "clinic_patient_name", "clinic_patient_family"),
    "patient_reference": ("clinic_patient_org_id", "clinic_patient_branch_id", "clinic_patient_name", "clinic_patient_family"),
}


def _reset_patient(state, *, reason):
    prior_step = state.get("clinic_input")
    if clear_flow(state, step_key="clinic_input", flow_key="clinic_flow",
                  flow_name=_PATIENT_FLOW, draft_keys=_PATIENT_DRAFT_KEYS):
        logger.info("clinic_flow_reset flow=patient_registration step=%s reason=%s",
                    prior_step or "unknown", reason)
    else:
        # Reject partially written legacy state without deleting other flows.
        for key in _PATIENT_DRAFT_KEYS:
            state.pop(key, None)
        if str(state.get("clinic_input") or "").startswith("patient_"):
            state.pop("clinic_input", None)
        if state.get("clinic_flow") == _PATIENT_FLOW:
            state.pop("clinic_flow", None)
        logger.info("clinic_flow_reset flow=patient_registration step=unknown reason=%s", reason)


def _patient_recovery_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 شروع مجدد ثبت بیمار", callback_data="clinic:new_patient")],
        [InlineKeyboardButton("◀️ بازگشت به منو", callback_data="clinic:menu")],
    ])


def _looks_like_url(text):
    return bool(re.search(r"(?:https?://|www\.|t\.me/|://)", text, flags=re.IGNORECASE))


def _valid_patient_input(step, value):
    if not value or len(value) > 120 or _looks_like_url(value):
        return False
    if step in {"patient_name", "patient_family"}:
        return value != "-" and not any(x in value for x in "/\\\\@")
    if step == "patient_phone":
        return value == "-" or bool(re.fullmatch(r"\+?[0-9۰-۹٠-٩ ()-]{7,25}", value))
    if step == "patient_reference":
        return value == "-" or bool(re.fullmatch(r"[\w .\-/]{1,80}", value, re.UNICODE))
    return False


async def _begin_patient(update, context):
    if context.user_data.get("clinic_patient_submitting"):
        await update.effective_message.reply_text("درخواست قبلی در حال ثبت است.")
        return
    scope = await _scope(update, context)
    branch_id = context.user_data.get("clinic_branch_id")
    if not branch_id:
        await update.effective_message.reply_text(
            "ابتدا شعبه کلینیک را در منو انتخاب کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return
    await scope.branch(branch_id, "patients.manage")
    start_flow(
        context.user_data, step_key="clinic_input", flow_key="clinic_flow",
        flow_name=_PATIENT_FLOW, initial_step="patient_name",
        draft_keys=_PATIENT_DRAFT_KEYS,
        initial_values={
            "clinic_patient_org_id": scope.organization_id,
            "clinic_patient_branch_id": branch_id,
        },
    )
    await update.effective_message.reply_text(
        "نام بیمار را ارسال کنید:", reply_markup=_patient_recovery_markup()
    )


async def _patient_input(update, context, step, value):
    state = context.user_data
    if not has_step(
        state, step_key="clinic_input", flow_key="clinic_flow",
        flow_name=_PATIENT_FLOW, step=step, required=_PATIENT_STEPS[step],
    ) or (step == "patient_reference" and "clinic_patient_phone" not in state):
        _reset_patient(state, reason="missing_or_invalid_stage")
        await update.effective_message.reply_text(
            "مراحل ثبت بیمار ناقص یا منقضی شده است. ثبت را دوباره شروع کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return
    if not _valid_patient_input(step, value):
        logger.info("clinic_flow_invalid_input flow=patient_registration step=%s reason=invalid_input", step)
        await update.effective_message.reply_text(
            "این ورودی برای مرحله فعلی معتبر نیست. لطفاً مقدار صحیح را ارسال کنید یا - را برای فیلد اختیاری بفرستید.",
            reply_markup=_patient_recovery_markup(),
        )
        return
    scope = await _scope(update, context)
    if state["clinic_patient_org_id"] != scope.organization_id or (
        state["clinic_patient_branch_id"] != state.get("clinic_branch_id")
    ):
        _reset_patient(state, reason="organization_or_branch_changed")
        await update.effective_message.reply_text(
            "شعبه یا کلینیک تغییر کرده است. ثبت بیمار را مجدد آغاز کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return
    if step == "patient_name":
        state["clinic_patient_name"] = value
        state["clinic_input"] = "patient_family"
        await update.effective_message.reply_text("نام خانوادگی بیمار را ارسال کنید:")
    elif step == "patient_family":
        state["clinic_patient_family"] = value
        state["clinic_input"] = "patient_phone"
        await update.effective_message.reply_text("شماره تماس بیمار را ارسال کنید یا - بفرستید:")
    elif step == "patient_phone":
        state["clinic_patient_phone"] = "" if value == "-" else value
        state["clinic_input"] = "patient_reference"
        await update.effective_message.reply_text("کد پرونده/شناسه بیمار را ارسال کنید یا - بفرستید:")
    elif step == "patient_reference":
        if state.get("clinic_patient_submitting"):
            await update.effective_message.reply_text(
                "درخواست ثبت بیمار در حال پردازش است.", reply_markup=_patient_recovery_markup()
            )
            return
        state["clinic_patient_submitting"] = True
        try:
            full_name = f"{state['clinic_patient_name']} {state['clinic_patient_family']}".strip()
            patient = await service.create_patient(
                scope, state["clinic_patient_branch_id"], full_name,
                phone=state["clinic_patient_phone"],
                external_reference=None if value == "-" else value,
            )
        except (ClinicAccessError, ValueError):
            logger.warning("clinic_flow_failed flow=patient_registration step=patient_reference reason=validation_or_access")
            await update.effective_message.reply_text(
                "ثبت بیمار انجام نشد. دسترسی یا اطلاعات شعبه را بررسی کنید و دوباره تلاش کنید.",
                reply_markup=_patient_recovery_markup(),
            )
            return
        except Exception:  # noqa: BLE001 - service boundary must retain draft and recover from unexpected storage errors
            logger.error("clinic_flow_failed flow=patient_registration step=patient_reference reason=service_error")
            await update.effective_message.reply_text(
                "در ثبت بیمار خطایی رخ داد. می‌توانید دوباره تلاش کنید یا از نو شروع کنید.",
                reply_markup=_patient_recovery_markup(),
            )
            return
        finally:
            state.pop("clinic_patient_submitting", None)
        _reset_patient(state, reason="completed")
        await update.effective_message.reply_text(
            f"✅ بیمار ثبت شد.\n👤 {patient.get('display_name', full_name)}\n\nآیا می‌خواهید برای او پرونده عملیاتی ایجاد کنید؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ایجاد پرونده", callback_data=f"clinic:new_case:{patient['id']}"),
                 InlineKeyboardButton("باز کردن بیمار", callback_data=f"clinic:patient:{patient['id']}")],
                [InlineKeyboardButton("بعداً", callback_data="clinic:menu")],
            ]),
        )


async def _scope(update, context):
    profile = context.application.bot_data.get("bot_config")
    if not profile or not profile.feature_enabled("healthcare"):
        raise ClinicAccessError("forbidden")
    memberships = await actor_scopes(str(update.effective_user.id), profile.key)
    oid = context.user_data.get("clinic_organization_id")
    if not oid and len({m["organization_id"] for m in memberships}) == 1:
        oid = memberships[0]["organization_id"]
        context.user_data["clinic_organization_id"] = oid
    if not oid or not any(m["organization_id"] == oid for m in memberships):
        raise ClinicAccessError("forbidden")
    return Scope(oid, str(update.effective_user.id))


async def _render(update, title, rows):
    markup = InlineKeyboardMarkup(rows)
    if update.callback_query:
        await update.callback_query.edit_message_text(title, reply_markup=markup)
    else:
        await update.effective_message.reply_text(title, reply_markup=markup)


async def _patient_list(update, context, scope, offset=0, search=None):
    page = await service.list_entities(scope, "patients", search=search, limit=8, offset=max(0, int(offset)))
    title = f"👥 بیماران\n{page['total']} بیمار"
    if search:
        title += f"\nنتیجه جست‌وجو برای: {search}"
    rows = [[InlineKeyboardButton(f"{item.get('display_name', 'بدون نام')} · {item.get('status', 'active')}", callback_data=f"clinic:patient:{item['id']}")] for item in page["items"]]
    if not rows:
        rows.append([InlineKeyboardButton("➕ ثبت بیمار جدید", callback_data="clinic:new_patient")])
        rows.append([InlineKeyboardButton("🔎 جست‌وجوی جدید", callback_data="clinic:patient_search")])
    nav = []
    if offset:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"clinic:patients:{max(0, offset-8)}"))
    if offset + 8 < page["total"]:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"clinic:patients:{offset+8}"))
    if nav: rows.append(nav)
    rows.extend([[InlineKeyboardButton("🔎 جست‌وجو", callback_data="clinic:patient_search")], [InlineKeyboardButton("➕ ثبت بیمار جدید", callback_data="clinic:new_patient")], [InlineKeyboardButton("◀️ کلینیک", callback_data="clinic:menu")]])
    await _render(update, title, rows)

async def clinic_menu(update, context):
    try:
        profile = context.application.bot_data.get("bot_config")
        if not profile or not profile.feature_enabled("healthcare"):
            raise ClinicAccessError("forbidden")
        memberships = await actor_scopes(str(update.effective_user.id), profile.key)
        # A newly enabled managed clinic bot may not have a workspace yet.
        # Bootstrap one for the configured administrator so /clinic is usable
        # immediately; regular users still require an explicit membership.
        if not memberships and is_admin(update.effective_user.id):
            await create_workspace(
                str(update.effective_user.id), profile.key,
                profile.name or "فضای کار کلینیک",
            )
            memberships = await actor_scopes(str(update.effective_user.id), profile.key)
        orgs = {m["organization_id"]: m["name"] for m in memberships}
        if (
            len(orgs) > 1
            and context.user_data.get("clinic_organization_id") not in orgs
        ):
            return await _render(
                update,
                "کلینیک را انتخاب کنید",
                [
                    [InlineKeyboardButton(name, callback_data=f"clinic:org:{oid}")]
                    for oid, name in orgs.items()
                ],
            )
        labels = profile.settings.get("terminology", {})
        scope = await _scope(update, context)
        branch_rows = await __import__("services.database", fromlist=["fetch_all_sql"]).fetch_all_sql("SELECT id,name FROM workspace_units WHERE workspace_id=? AND status='active' ORDER BY name", (scope.organization_id,))
        selected_branch = context.user_data.get("clinic_branch_id")
        if not branch_rows:
            can_manage = any(m.get("role") in {"owner", "manager", "admin"} for m in memberships)
            rows = [[InlineKeyboardButton("➕ تعریف شعبه کلینیک", callback_data="clinic:new_branch")]] if can_manage else []
            return await _render(update, "برای ثبت بیمار ابتدا یک شعبه کلینیک تعریف کنید.", rows)
        if not selected_branch or not any(str(b["id"]) == str(selected_branch) for b in branch_rows):
            return await _render(update, "شعبه کلینیک را انتخاب کنید:", [[InlineKeyboardButton(b["name"], callback_data=f"clinic:branch:{b['id']}")] for b in branch_rows])
        metrics = await reports.metrics(scope, unit_id=selected_branch)
        total_patients = (await service.list_entities(scope, "patients", unit_id=selected_branch, limit=1))["total"]
        open_cases = int(metrics.get("cases", {}).get("total", 0) - metrics.get("cases", {}).get("completed", 0))
        followups_today = int(metrics.get("followups", {}).get("total", 0))
        overdue = int(metrics.get("followups", {}).get("overdue", 0))
        dashboard = (f"🏥 {labels.get('workspace', 'کلینیک')}\n\n👥 بیماران: {total_patients}\n📂 پرونده‌های باز: {max(0, open_cases)}\n⏰ پیگیری‌های امروز: {followups_today}\n⚠️ عقب‌افتاده: {overdue}")
        rows = [
            [InlineKeyboardButton("➕ ثبت بیمار", callback_data="clinic:new_patient"), InlineKeyboardButton("🔎 جست‌وجوی بیمار", callback_data="clinic:patient_search")],
            [InlineKeyboardButton("👥 بیماران", callback_data="clinic:patients:0"), InlineKeyboardButton("📂 پرونده‌ها", callback_data="clinic:cases:0")],
            [InlineKeyboardButton("🗓️ جلسات", callback_data="clinic:typed:0"), InlineKeyboardButton("⏰ پیگیری‌ها", callback_data="clinic:queue:today:0")],
        ]
        if any(
            m["role"] in {"owner", "manager", "admin"}
            and m["organization_id"] == scope.organization_id
            for m in memberships
        ):
            rows.append(
                [InlineKeyboardButton("خلاصه مدیریت", callback_data="clinic:metrics")]
            )
        await scope.predicate("followups.view", doctor_context="?=?")
        await _render(update, dashboard, rows)
    except ClinicAccessError:
        await update.effective_message.reply_text("دسترسی مجاز به کلینیک پیدا نشد.")

async def handle_clinic_input(update, context):
    step = context.user_data.get("clinic_input")
    if not step or not update.effective_message or not update.effective_message.text:
        return False
    value = update.effective_message.text.strip()
    if step in _PATIENT_STEPS:
        try:
            await _patient_input(update, context, step, value)
        except ClinicAccessError:
            _reset_patient(context.user_data, reason="access_revoked")
            await update.effective_message.reply_text(
                "دسترسی شما به کلینیک یا شعبه برقرار نیست. از منو دوباره شروع کنید.",
                reply_markup=_patient_recovery_markup(),
            )
        return True
    if str(step).startswith("patient_") or step not in {
        "branch_name", "patient_search", "followup_title", "followup_custom_date",
        "typed_session_title", "typed_session_custom_date", "typed_case_title",
        "typed_reschedule",
    }:
        logger.warning("clinic_flow_reset flow=clinic step=%s reason=unknown_step", str(step)[:50])
        _reset_patient(context.user_data, reason="unknown_step")
        context.user_data.pop("clinic_input", None)
        await update.effective_message.reply_text(
            "مرحله مکالمه نامعتبر یا منقضی شده است. از منو دوباره شروع کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return True
    required = {
        "followup_title": ("clinic_case_id",),
        "followup_custom_date": ("clinic_case_id", "clinic_followup_title"),
        "typed_session_title": ("clinic_patient_id",),
        "typed_session_custom_date": ("clinic_patient_id", "clinic_session_title"),
        "typed_case_title": ("clinic_patient_id",),
        "typed_reschedule": ("clinic_reschedule_task_id",),
    }
    if any(not context.user_data.get(key) for key in required.get(step, ())):
        logger.info("clinic_flow_reset flow=clinic step=%s reason=missing_prerequisite", step)
        context.user_data.pop("clinic_input", None)
        await update.effective_message.reply_text(
            "اطلاعات این مرحله ناقص یا منقضی شده است؛ از منو دوباره شروع کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return True
    profile = context.application.bot_data.get("bot_config")
    try:
        memberships = await actor_scopes(str(update.effective_user.id), profile.key)
        if not memberships: raise ClinicAccessError("forbidden")
        if step == "branch_name":
            scope = Scope(memberships[0]["organization_id"], str(update.effective_user.id))
            branch_id = await service.create_branch(scope, value)
            context.user_data["clinic_branch_id"] = branch_id
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text("✅ شعبه کلینیک تعریف شد.")
            await clinic_menu(update, context)
        elif step == "patient_search":
            context.user_data.pop("clinic_input", None)
            await _patient_list(update, context, Scope(memberships[0]["organization_id"], str(update.effective_user.id)), 0, value)
        elif step == "followup_title":
            context.user_data["clinic_followup_title"] = value
            context.user_data["clinic_input"] = "followup_date"
            case_id = context.user_data["clinic_case_id"]
            await update.effective_message.reply_text("📅 موعد پیگیری را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(deadline_label(i), callback_data=f"clinic:followup_date:{case_id}:{i}") for i in range(4)], [InlineKeyboardButton("تاریخ دلخواه شمسی", callback_data=f"clinic:followup_date:{case_id}:custom"), InlineKeyboardButton("لغو", callback_data=f"clinic:case:{case_id}")]]))
        elif step == "followup_custom_date":
            from utils.date_parse import parse_deadline_input
            due = parse_deadline_input(value)
            if not due: raise ValueError("invalid_date")
            scope = Scope(memberships[0]["organization_id"], str(update.effective_user.id))
            case_id = context.user_data.get("clinic_case_id")
            title = context.user_data.get("clinic_followup_title")
            await followups.create_followup(scope, case_id, str(update.effective_user.id), due, title=title)
            for key in ("clinic_case_id", "clinic_followup_title", "clinic_input"):
                context.user_data.pop(key, None)
            await update.effective_message.reply_text("✅ پیگیری ثبت شد.")
        elif step == "typed_session_title":
            context.user_data["clinic_session_title"] = value
            context.user_data["clinic_input"] = "typed_session_date"
            await update.effective_message.reply_text("📅 تاریخ جلسه را انتخاب کنید:\nجلسه یک نوبت مشخص از مراجعه بیمار است؛ پرونده عملیاتی برای پیگیری بلندمدت استفاده می‌شود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("امروز", callback_data="clinic:session_date:0"), InlineKeyboardButton("فردا", callback_data="clinic:session_date:1")], [InlineKeyboardButton("۳ روز بعد", callback_data="clinic:session_date:3"), InlineKeyboardButton("انتخاب تاریخ شمسی", callback_data="clinic:session_date:custom")], [InlineKeyboardButton("بدون تاریخ", callback_data="clinic:session_date:none")]]))
        elif step == "typed_session_custom_date":
            from utils.date_parse import parse_deadline_input
            scheduled = parse_deadline_input(value)
            if not scheduled: raise ValueError("invalid_date")
            scope = Scope(memberships[0]["organization_id"], str(update.effective_user.id))
            patient_id = context.user_data.get("clinic_patient_id")
            title = context.user_data.get("clinic_session_title")
            typed_patient = await clinic_typed.ensure_typed_patient_for_legacy_async(
                scope, patient_id
            )
            await clinic_typed.create_child_async(
                scope,
                typed_patient["id"],
                "session",
                title,
                scheduled_at=scheduled,
                doctor_id=typed_patient.get("assignee_id"),
            )
            for key in ("clinic_patient_id", "clinic_session_title", "clinic_input"):
                context.user_data.pop(key, None)
            await update.effective_message.reply_text("✅ جلسه بیمار برای تاریخ شمسی انتخاب‌شده ایجاد شد.")
        elif step == "typed_case_title":
            scope = Scope(memberships[0]["organization_id"], str(update.effective_user.id))
            patient_id = context.user_data.get("clinic_patient_id")
            await service.create_case(scope, patient_id, value, str(update.effective_user.id))
            context.user_data.pop("clinic_patient_id", None)
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text("✅ پرونده عملیاتی بیمار ایجاد شد.")
        elif step == "typed_reschedule":
            task_id = context.user_data.get("clinic_reschedule_task_id")
            await clinic_typed.reschedule_async(task_id, str(update.effective_user.id), value)
            context.user_data.pop("clinic_reschedule_task_id", None)
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text("✅ زمان جلسه تغییر کرد.")
        else:
            logger.warning("clinic_flow_reset flow=clinic step=%s reason=unhandled_step", str(step)[:50])
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text(
                "این مرحله قابل انجام نیست. از منو دوباره شروع کنید.",
                reply_markup=_patient_recovery_markup(),
            )
        return True
    except (ClinicAccessError, ValueError):
        logger.info("clinic_flow_failed flow=clinic step=%s reason=invalid_input_or_access", step)
        await update.effective_message.reply_text(
            "این عملیات انجام نشد. ورودی یا دسترسی را بررسی کنید؛ برای شروع مجدد از منو استفاده کنید.",
            reply_markup=_patient_recovery_markup(),
        )
        return True


async def clinic_callback(update, context):
    query = update.callback_query
    await query.answer()
    try:
        parts = (query.data or "").split(":")
        if query.data == "clinic:new_branch":
            context.user_data["clinic_input"] = "branch_name"
            return await query.message.reply_text("نام شعبه کلینیک را ارسال کنید:")
        if query.data == "clinic:new_patient":
            return await _begin_patient(update, context)
        if query.data == "clinic:cancel_patient":
            _reset_patient(context.user_data, reason="cancelled")
            return await query.message.reply_text(
                "ثبت بیمار لغو شد.", reply_markup=_patient_recovery_markup()
            )
        if parts[1] == "branch":
            scope = await _scope(update, context)
            await scope.branch(parts[2], "patients.view")
            _reset_patient(context.user_data, reason="branch_changed")
            context.user_data["clinic_branch_id"] = parts[2]
            return await clinic_menu(update, context)
        if parts[1] == "org":
            profile = context.application.bot_data.get("bot_config")
            if not profile or not profile.feature_enabled("healthcare"):
                raise ClinicAccessError("forbidden")
            memberships = await actor_scopes(str(update.effective_user.id), profile.key)
            if not any(m["organization_id"] == parts[2] for m in memberships):
                raise ClinicAccessError("forbidden")
            _reset_patient(context.user_data, reason="organization_changed")
            context.user_data["clinic_organization_id"] = parts[2]
            context.user_data.pop("clinic_branch_id", None)
            return await clinic_menu(update, context)
        scope = await _scope(update, context)
        if parts[1] == "menu":
            _reset_patient(context.user_data, reason="menu")
            return await clinic_menu(update, context)
        if parts[1] == "metrics":
            data = await reports.metrics(scope)
            message = (
                f"اقدام‌های باز: {data['tasks']['total'] - data['tasks']['completed']}\n"
                f"اقدام‌های عقب‌افتاده: {data['tasks']['overdue']}\n"
                f"پرونده‌های بدون اقدام بعدی: {data['cases']['missing_next_action']}\n"
                f"پیگیری‌های عقب‌افتاده: {data['followups']['overdue']}"
            )
            return await _render(
                update,
                message,
                [[InlineKeyboardButton("منو", callback_data="clinic:menu")]],
            )
        if parts[1] == "typed":
            offset = max(0, int(parts[2]))
            from services.database import fetch_all_sql
            from services.work_item_access import workspace_predicate
            pred, args = await workspace_predicate(scope.workspace_id, str(update.effective_user.id), alias="t", action="view")
            params = list(args)
            filters = [pred, "t.work_item_type='session'", "t.archived_at IS NULL"]
            selected_branch = context.user_data.get("clinic_branch_id")
            if selected_branch:
                filters.append("t.unit_id=?")
                params.append(selected_branch)
            # pred is generated by workspace_predicate; all user values are bound in params.
            sql = (
                "SELECT t.* FROM tasks t WHERE " + " AND ".join(filters)  # nosec B608
                + " ORDER BY COALESCE(t.deadline,t.created_at),t.id LIMIT ? OFFSET ?"
            )
            rows = await fetch_all_sql(sql, tuple(params) + (7, offset))
            visible = rows[:6]
            buttons = [[InlineKeyboardButton(f"{r['title']} · {r['status']}", callback_data=f"clinic:typed_item:{r['id']}")] for r in visible]
            nav = []
            if offset:
                nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"clinic:typed:{max(0, offset-6)}"))
            if len(rows) > 6:
                nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"clinic:typed:{offset+6}"))
            if nav:
                buttons.append(nav)
            buttons.append([InlineKeyboardButton("منو", callback_data="clinic:menu")])
            return await _render(update, "🗓️ جلسات", buttons)
        if parts[1] == "typed_item":
            item = await clinic_typed._item(parts[2], str(update.effective_user.id))
            buttons = []
            if item.get("work_item_type") == "session":
                buttons.extend([[InlineKeyboardButton("✅ تکمیل", callback_data=f"clinic:typed_status:{item['id']}:completed")], [InlineKeyboardButton("📅 تغییر زمان", callback_data=f"clinic:typed_reschedule:{item['id']}")]])
            elif item.get("work_item_type") == "followup":
                buttons.append([InlineKeyboardButton("✅ تکمیل", callback_data=f"clinic:typed_status:{item['id']}:completed")])
            buttons.append([InlineKeyboardButton("منو", callback_data="clinic:menu")])
            return await _render(update, f"{item['title']}\nوضعیت: {item['status']}", buttons)
        if parts[1] == "typed_status":
            await clinic_typed.transition_async(parts[2], str(update.effective_user.id), parts[3])
            return await _render(update, "✅ وضعیت ثبت شد.", [[InlineKeyboardButton("منو", callback_data="clinic:menu")]])
        if parts[1] == "typed_reschedule":
            context.user_data["clinic_reschedule_task_id"] = parts[2]
            context.user_data["clinic_input"] = "typed_reschedule"
            return await query.message.reply_text("زمان جدید جلسه را با قالب ISO ارسال کنید (مثلاً 2026-10-08T10:00:00+03:30):")
        if parts[1] == "queue":
            view, offset = parts[2], max(0, int(parts[3]))
            page = await followups.queue(scope, view, limit=6, offset=offset)
            rows = [
                [
                    InlineKeyboardButton(
                        f"{f['due_at'][:10]} · پیگیری {f['attempt_number']}",
                        callback_data=f"clinic:followup:{f['id']}",
                    )
                ]
                for f in page["items"]
            ]
            if offset:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "قبلی",
                            callback_data=f"clinic:queue:{view}:{max(0, offset - 6)}",
                        )
                    ]
                )
            if offset + 6 < page["total"]:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "بعدی", callback_data=f"clinic:queue:{view}:{offset + 6}"
                        )
                    ]
                )
            rows.append([InlineKeyboardButton("منو", callback_data="clinic:menu")])
            return await _render(update, f"صف پیگیری · {page['total']} مورد", rows)
        if parts[1] == "patients":
            return await _patient_list(update, context, scope, max(0, int(parts[2])))
        if parts[1] == "patient_search":
            context.user_data["clinic_input"] = "patient_search"
            return await query.message.reply_text("🔎 نام بیمار، شماره تماس یا شناسه پرونده را ارسال کنید:")
        if parts[1] == "cases":
            kind, offset = parts[1], max(0, int(parts[2]))
            page = await service.list_entities(scope, kind, limit=8, offset=offset)
            rows = [[InlineKeyboardButton(f"{x.get('title')} · {x.get('status')}", callback_data=f"clinic:case:{x['id']}")] for x in page["items"]]
            rows.append([InlineKeyboardButton("◀️ کلینیک", callback_data="clinic:menu")])
            return await _render(update, f"📂 پرونده‌های عملیاتی\n{page['total']} مورد", rows)
        if parts[1] == "patient":
            patient = await service.get_entity(scope, "patients", parts[2])
            from services.database import fetch_all_sql
            cases = await fetch_all_sql("SELECT id,title,status,expected_at FROM cases WHERE workspace_id=? AND reference_id=? ORDER BY created_at DESC LIMIT 10", (scope.workspace_id, parts[2]))
            typed_patient = await clinic_typed.find_typed_patient_for_legacy_async(
                scope, parts[2]
            )
            sessions = (
                await clinic_typed.list_children_async(
                    typed_patient["id"], str(update.effective_user.id),
                    item_type="session", limit=10
                )
                if typed_patient else {"items": [], "total": 0}
            )
            lines = [f"👤 {patient.get('display_name')}\nوضعیت: {patient.get('status')}"]
            if sessions["items"]:
                lines.append("\n🗓️ جلسات:\n" + "\n".join(
                    f"• {x['title']} · {x['status']}" for x in sessions["items"]
                ))
            if cases:
                lines.append("\n📂 پرونده‌های عملیاتی:\n" + "\n".join(
                    f"• {x['title']} · {x['status']}" for x in cases
                ))
            if not sessions["items"] and not cases:
                lines.append("هنوز جلسه یا پرونده عملیاتی ثبت نشده است.")
            rows = [[
                InlineKeyboardButton("➕ ایجاد جلسه", callback_data=f"clinic:new_session:{parts[2]}"),
                InlineKeyboardButton("📁 ایجاد پرونده عملیاتی", callback_data=f"clinic:new_case:{parts[2]}")
            ]]
            rows.extend([
                [InlineKeyboardButton(
                    f"🗓️ {x['title']} · {x['status']}",
                    callback_data=f"clinic:typed_item:{x['id']}"
                )]
                for x in sessions["items"][:5]
            ])
            rows.append([InlineKeyboardButton("بازگشت", callback_data="clinic:patients:0")])
            return await _render(update, "\n".join(lines), rows)
        if parts[1] == "session_date":
            if context.user_data.get("clinic_input") != "typed_session_date":
                raise ValueError("session_date_expired")
            choice = parts[2]
            if choice == "custom":
                context.user_data["clinic_input"] = "typed_session_custom_date"
                return await query.message.reply_text("تاریخ را به شمسی وارد کنید؛ مثال: ۱۴۰۵/۰۷/۱۵ یا 1405-07-15")
            scope = await _scope(update, context)
            patient_id = context.user_data.get("clinic_patient_id")
            title = context.user_data.get("clinic_session_title")
            if not patient_id or not title:
                raise ValueError("session_draft_expired")
            expected = None if choice == "none" else (datetime.now(timezone.utc) + timedelta(days=int(choice))).date().isoformat()
            typed_patient = await clinic_typed.ensure_typed_patient_for_legacy_async(
                scope, patient_id
            )
            await clinic_typed.create_child_async(
                scope,
                typed_patient["id"],
                "session",
                title,
                scheduled_at=expected,
                doctor_id=typed_patient.get("assignee_id"),
            )
            for key in ("clinic_patient_id", "clinic_session_title", "clinic_input"):
                context.user_data.pop(key, None)
            return await query.message.reply_text("✅ جلسه بیمار ایجاد شد.")
        if parts[1] == "new_session":
            context.user_data["clinic_patient_id"] = parts[2]
            context.user_data["clinic_input"] = "typed_session_title"
            return await query.message.reply_text("عنوان جلسه را ارسال کنید:")
        if parts[1] == "new_case":
            context.user_data["clinic_patient_id"] = parts[2]
            context.user_data["clinic_input"] = "typed_case_title"
            return await query.message.reply_text("📁 پرونده عملیاتی برای یک روند چندمرحله‌ای بیمار است و می‌تواند چند جلسه، اقدام و پیگیری داشته باشد.\n\nعنوان پرونده عملیاتی را ارسال کنید:")
        if parts[1] == "case":
            case = await service.get_entity(scope, "cases", parts[2])
            patient = await service.get_entity(scope, "patients", case["reference_id"])
            status_labels = {"active": "🟡 در حال انجام", "waiting": "⏳ منتظر", "blocked": "🔴 مسدود", "completed": "✅ تکمیل‌شده", "closed": "⚪ بسته‌شده", "cancelled": "🚫 لغوشده"}
            text_body = f"📂 {case.get('title')}\n\nبیمار: {patient.get('display_name')}\nوضعیت پرونده: {status_labels.get(case.get('status'), case.get('status'))}\nمسئول: {case.get('primary_owner_user_id') or 'تعیین نشده'}"
            rows = [[InlineKeyboardButton("⏰ پیگیری‌ها", callback_data=f"clinic:case_followups:{case['id']}:0"), InlineKeyboardButton("➕ پیگیری جدید", callback_data=f"clinic:new_followup:{case['id']}")], [InlineKeyboardButton("🟡 در حال انجام", callback_data=f"clinic:case_status:{case['id']}:active"), InlineKeyboardButton("⏳ منتظر", callback_data=f"clinic:case_status:{case['id']}:waiting")], [InlineKeyboardButton("✅ تکمیل", callback_data=f"clinic:case_status:{case['id']}:completed"), InlineKeyboardButton("⚪ بستن", callback_data=f"clinic:case_status:{case['id']}:closed")], [InlineKeyboardButton("👤 بیمار", callback_data=f"clinic:patient:{patient['id']}"), InlineKeyboardButton("◀️ پرونده‌ها", callback_data="clinic:cases:0")]]
            return await _render(update, text_body, rows)
        if parts[1] == "new_followup":
            context.user_data["clinic_case_id"] = parts[2]
            context.user_data["clinic_input"] = "followup_title"
            return await query.message.reply_text("عنوان پیگیری را ارسال کنید:")
        if parts[1] == "followup_date":
            if context.user_data.get("clinic_input") != "followup_date": raise ValueError("followup_date_expired")
            case_id, choice = parts[2], parts[3]
            if choice == "custom":
                context.user_data["clinic_case_id"] = case_id
                context.user_data["clinic_input"] = "followup_custom_date"
                return await query.message.reply_text("تاریخ شمسی را وارد کنید؛ مثال: ۱۴۰۵/۰۷/۱۵")
            scope = await _scope(update, context)
            title = context.user_data.get("clinic_followup_title")
            if not title or context.user_data.get("clinic_case_id") != case_id:
                raise ValueError("followup_draft_expired")
            due = deadline_value(int(choice))
            await followups.create_followup(scope, case_id, str(update.effective_user.id), due, title=title)
            for key in ("clinic_case_id", "clinic_followup_title", "clinic_input"):
                context.user_data.pop(key, None)
            return await query.message.reply_text("✅ پیگیری ثبت شد.")
        if parts[1] == "case_followups":
            scope = await _scope(update, context)
            page = await followups.queue(scope, "upcoming", case_id=parts[2], limit=8, offset=int(parts[3]))
            rows = [[InlineKeyboardButton(f"{x.get('due_at','')[:10]} · {x.get('title','پیگیری')} · {x.get('status')}", callback_data=f"clinic:followup:{x['id']}")] for x in page["items"]]
            rows.append([InlineKeyboardButton("➕ پیگیری جدید", callback_data=f"clinic:new_followup:{parts[2]}"), InlineKeyboardButton("◀️ پرونده", callback_data=f"clinic:case:{parts[2]}")])
            return await _render(update, f"⏰ پیگیری‌های پرونده ({page['total']})", rows)
        if parts[1] == "case_status":
            await service.set_case_status(scope, parts[2], parts[3])
            return await _render(update, "✅ وضعیت پرونده تغییر کرد.", [[InlineKeyboardButton("باز کردن پرونده", callback_data=f"clinic:case:{parts[2]}"), InlineKeyboardButton("◀️ پرونده‌ها", callback_data="clinic:cases:0")]])
        if parts[1] == "followup":
            item = await service.get_entity(scope, "followups", parts[2])
            case = await service.get_entity(scope, "cases", item["case_id"])
            rows = [
                [
                    InlineKeyboardButton(
                        label, callback_data=f"clinic:out:{item['id']}:{key}"
                    )
                ]
                for key, label in [
                    ("reached", "ارتباط برقرار شد"),
                    ("no_answer", "جواب نداد"),
                    ("needs_time", "زمان جدید"),
                    ("escalated", "نیاز به بررسی مسئول"),
                    ("closed", "بستن پیگیری"),
                ]
            ]
            return await _render(
                update,
                f"{case['title']}\nموعد: {item['due_at']}\nتلاش: {item['attempt_number']}",
                rows,
            )
        if parts[1] in {"out", "retry"}:
            fid, key = parts[2:4]
            # Recheck backend permission before displaying or executing a write.
            await service.get_entity(scope, "followups", fid, manage=True)
            if parts[1] == "out" and service.OUTCOMES.get(key, ("", False))[1]:
                return await _render(
                    update,
                    "ثبت نتیجه و زمان اقدام بعدی را تأیید کنید:",
                    [
                        [
                            InlineKeyboardButton(
                                label, callback_data=f"clinic:retry:{fid}:{key}:{days}"
                            )
                        ]
                        for days, label in [
                            (1, "تأیید · ۲۴ ساعت بعد"),
                            (7, "تأیید · ۷ روز بعد"),
                        ]
                    ],
                )
            due = None
            if parts[1] == "retry":
                days = int(parts[4])
                if days not in {1, 7}:
                    raise ValueError("invalid_retry")
                due = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
            await followups.record_outcome(scope, fid, key, next_due_at=due)
            return await _render(
                update,
                "نتیجه ثبت شد.",
                [
                    [
                        InlineKeyboardButton(
                            "صف امروز", callback_data="clinic:queue:today:0"
                        )
                    ]
                ],
            )
        raise ValueError("invalid_callback")
    except (ClinicAccessError, ValueError, IndexError):
        await query.edit_message_text("این اقدام مجاز نیست یا اطلاعات آن معتبر نیست.")
