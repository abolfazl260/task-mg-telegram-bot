"""Minimal role-scoped clinic execution menu using the shared domain service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.healthcare import followups, reports, service
from services import clinic_typed
from services.healthcare.access import ClinicAccessError, Scope, actor_scopes
from services.operations.service import create_workspace
from services.permission_service import is_admin


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
        branches = await service.list_entities(scope, "patients", limit=1)
        branch_rows = await __import__("services.database", fromlist=["fetch_all_sql"]).fetch_all_sql("SELECT id,name FROM workspace_units WHERE workspace_id=? AND status='active' ORDER BY name", (scope.organization_id,))
        selected_branch = context.user_data.get("clinic_branch_id")
        if not branch_rows:
            can_manage = any(m.get("role") in {"owner", "manager", "admin"} for m in memberships)
            rows = [[InlineKeyboardButton("➕ تعریف شعبه کلینیک", callback_data="clinic:new_branch")]] if can_manage else []
            return await _render(update, "برای ثبت بیمار ابتدا یک شعبه کلینیک تعریف کنید.", rows)
        if not selected_branch or not any(str(b["id"]) == str(selected_branch) for b in branch_rows):
            return await _render(update, "شعبه کلینیک را انتخاب کنید:", [[InlineKeyboardButton(b["name"], callback_data=f"clinic:branch:{b['id']}")] for b in branch_rows])
        rows = [
            [
                InlineKeyboardButton(
                    "پیگیری‌های امروز", callback_data="clinic:queue:today:0"
                ),
                InlineKeyboardButton(
                    "عقب‌افتاده", callback_data="clinic:queue:overdue:0"
                ),
            ],
            [
                InlineKeyboardButton("آینده", callback_data="clinic:queue:upcoming:0"),
                InlineKeyboardButton(
                    "جواب نداد", callback_data="clinic:queue:no_answer:0"
                ),
            ],
            [
                InlineKeyboardButton(
                    labels.get("patient", "بیمار"), callback_data="clinic:patients:0"
                ),
                InlineKeyboardButton(
                    labels.get("case", "پرونده عملیاتی"), callback_data="clinic:cases:0"
                ),
            ],
            [InlineKeyboardButton("🗓️ جلسات و پیگیری‌های تایپ‌شده", callback_data="clinic:typed:0")],
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
        await _render(update, labels.get("workspace", "فضای کار کلینیک"), rows)
    except ClinicAccessError:
        await update.effective_message.reply_text("دسترسی مجاز به کلینیک پیدا نشد.")

async def handle_clinic_input(update, context):
    step = context.user_data.get("clinic_input")
    if not step or not update.effective_message or not update.effective_message.text:
        return False
    value = update.effective_message.text.strip()
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
        elif step == "patient_name":
            context.user_data["clinic_patient_name"] = value
            context.user_data["clinic_input"] = "patient_family"
            await update.effective_message.reply_text("نام خانوادگی بیمار را ارسال کنید:")
        elif step == "patient_family":
            context.user_data["clinic_patient_family"] = value
            context.user_data["clinic_input"] = "patient_phone"
            await update.effective_message.reply_text("شماره تماس بیمار را ارسال کنید یا - بفرستید:")
        elif step == "patient_phone":
            context.user_data["clinic_patient_phone"] = "" if value == "-" else value
            context.user_data["clinic_input"] = "patient_reference"
            await update.effective_message.reply_text("کد پرونده/شناسه بیمار را ارسال کنید یا - بفرستید:")
        elif step == "typed_reschedule":
            task_id = context.user_data.pop("clinic_reschedule_task_id")
            await clinic_typed.reschedule_async(task_id, str(update.effective_user.id), value)
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text("✅ زمان جلسه تغییر کرد.")
        else:
            unit_id = context.user_data.get("clinic_branch_id") or next((m.get("branch_id") for m in memberships if m.get("branch_id")), None)
            if not unit_id: raise ValueError("branch_required")
            full_name = f"{context.user_data.pop('clinic_patient_name')} {context.user_data.pop('clinic_patient_family')}".strip()
            item = await service.create_patient(Scope(memberships[0]["organization_id"], str(update.effective_user.id)), unit_id, full_name, phone=context.user_data.pop("clinic_patient_phone", ""), external_reference=None if value == "-" else value)
            context.user_data.pop("clinic_input", None)
            await update.effective_message.reply_text(f"✅ بیمار ثبت شد.\nشناسه: {item['id']}")
        return True
    except (ClinicAccessError, ValueError):
        context.user_data.pop("clinic_input", None)
        await update.effective_message.reply_text("ثبت بیمار انجام نشد؛ ابتدا شعبه کلینیک را تعریف کنید.")
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
            context.user_data["clinic_input"] = "patient_name"
            return await query.message.reply_text("نام و نام خانوادگی بیمار را ارسال کنید:")
        if parts[1] == "branch":
            scope = await _scope(update, context)
            await scope.branch(parts[2], "patients.view")
            context.user_data["clinic_branch_id"] = parts[2]
            return await clinic_menu(update, context)
        if parts[1] == "org":
            profile = context.application.bot_data.get("bot_config")
            if not profile or not profile.feature_enabled("healthcare"):
                raise ClinicAccessError("forbidden")
            memberships = await actor_scopes(str(update.effective_user.id), profile.key)
            if not any(m["organization_id"] == parts[2] for m in memberships):
                raise ClinicAccessError("forbidden")
            context.user_data["clinic_organization_id"] = parts[2]
            return await clinic_menu(update, context)
        scope = await _scope(update, context)
        if parts[1] == "menu":
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
            from services.work_item_access import workspace_predicate
            from services.database import fetch_all_sql
            pred, args = await workspace_predicate(scope.workspace_id, str(update.effective_user.id), alias="t", action="view")
            rows = await fetch_all_sql("SELECT t.* FROM tasks t WHERE " + pred + " AND t.work_item_type IN ('session','followup') AND t.archived_at IS NULL ORDER BY COALESCE(t.deadline,t.created_at),t.id LIMIT ? OFFSET ?", args + (6, offset))
            buttons = [[InlineKeyboardButton(f"{r['title']} · {r['status']}", callback_data=f"clinic:typed_item:{r['id']}")] for r in rows]
            buttons.append([InlineKeyboardButton("منو", callback_data="clinic:menu")])
            return await _render(update, "جلسات و پیگیری‌ها", buttons)
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
        if parts[1] in {"patients", "cases"}:
            kind, offset = parts[1], max(0, int(parts[2]))
            page = await service.list_entities(scope, kind, limit=6, offset=offset)
            lines = [
                f"{item.get('display_name') or item.get('title')} · {item['status']}"
                for item in page["items"]
            ]
            rows = []
            if offset:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "قبلی", callback_data=f"clinic:{kind}:{max(0, offset - 6)}"
                        )
                    ]
                )
            if offset + 6 < page["total"]:
                rows.append(
                    [
                        InlineKeyboardButton(
                            "بعدی", callback_data=f"clinic:{kind}:{offset + 6}"
                        )
                    ]
                )
            if kind == "patients":
                rows.insert(0, [InlineKeyboardButton("➕ ثبت بیمار جدید", callback_data="clinic:new_patient")])
            rows.append([InlineKeyboardButton("منو", callback_data="clinic:menu")])
            return await _render(update, "\n".join(lines) or "موردی وجود ندارد.", rows)
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
