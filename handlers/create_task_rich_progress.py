"""Progress and media presentation for the manual Rich create-task flow."""

from html import escape
import sys


def _description_media(context):
    items = context.user_data.get("description_media") or []
    return items if isinstance(items, list) else []


def _rich_media_payload(context):
    payload = []
    for index, item in enumerate(_description_media(context)):
        if item.get("type") not in {"photo", "video"} or not item.get("file_id"):
            continue
        media_id = f"desc_media_{index}"
        payload.append({
            "id": media_id,
            "media": {"type": item["type"], "media": item["file_id"]},
        })
    return payload


def _description_media_html(context):
    items = _description_media(context)
    blocks = []
    for index, item in enumerate(items):
        kind = item.get("type")
        if kind in {"photo", "video"} and item.get("file_id"):
            media_id = f"desc_media_{index}"
            if kind == "photo":
                blocks.append(f'<img src="tg://photo?id={media_id}"/>')
            else:
                blocks.append(f'<video src="tg://video?id={media_id}"></video>')
            caption = str(item.get("caption") or "").strip()
            if caption:
                blocks.append(f'<p>💬 {escape(caption[:500])}</p>')
        elif kind == "location":
            try:
                lat = float(item.get("latitude"))
                lon = float(item.get("longitude"))
                blocks.append(f'<tg-map lat="{lat}" long="{lon}" zoom="14"/>')
                blocks.append(f'<p>📍 موقعیت: <code>{lat:.6f}, {lon:.6f}</code></p>')
            except (TypeError, ValueError):
                continue
    if not blocks:
        return ""
    return '<p><b>📎 پیوست‌های توضیحات</b></p>' + "".join(blocks)


def _draft_summary(context):
    task = context.user_data.get("new_task") or {}
    if not isinstance(task, dict):
        return ""

    labels = []
    title = str(task.get("title") or "").strip()
    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"))
    deadline = str(task.get("deadline") or "").strip()
    category = str(task.get("category") or "").strip()
    tags = str(task.get("tags") or "").strip()
    description = str(task.get("description") or "").strip()
    assignee = task.get("assignee")

    if title:
        labels.append(f"📝 <b>عنوان:</b> {escape(title)}")
    if priority:
        labels.append(f"🎯 <b>اولویت:</b> {escape(priority)}")
    if deadline:
        labels.append(f"📅 <b>زمان:</b> {escape(deadline)}")
    if category:
        labels.append(f"📂 <b>دسته‌بندی:</b> {escape(category)}")
    if tags:
        labels.append(f"🏷 <b>تگ:</b> {escape(tags)}")
    if description:
        labels.append(f"📄 <b>توضیحات:</b> {escape(description[:500])}")

    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or assignee.get("user_id")
        if name:
            labels.append(f"👤 <b>مسئول:</b> {escape(str(name))}")
    elif assignee is None and "assignee" in task:
        labels.append("👤 <b>مسئول:</b> بدون مسئول")

    media_html = _description_media_html(context)
    if not labels and not media_html:
        return ""
    text = '<p><b>📋 اطلاعات ثبت‌شده</b></p>' + "".join(f"<p>{line}</p>" for line in labels)
    if media_html:
        text += media_html
    return text + "<p>━━━━━━━━━━━━</p>"


def _summary_rich_html(task):
    assignee = task.get("assignee")
    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or str(assignee.get("user_id") or "کاربر")
    else:
        name = "بدون مسئول"

    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), "—")
    return (
        '<p><b>📋 خلاصه وظیفه</b></p>'
        '<p>اطلاعات زیر را قبل از ثبت بررسی کنید:</p>'
        '<p>━━━━━━━━━━━━━━━━</p>'
        f'<p>📝 <b>عنوان</b><br>{escape(str(task.get("title") or "—"))}</p>'
        f'<p>🎯 <b>اولویت</b><br>{escape(priority)}</p>'
        f'<p>📅 <b>زمان انجام</b><br>{escape(str(task.get("deadline") or "بدون زمان‌بندی"))}</p>'
        f'<p>📂 <b>دسته‌بندی</b><br>{escape(str(task.get("category") or "بدون دسته‌بندی"))}</p>'
        f'<p>🏷 <b>تگ</b><br>{escape(str(task.get("tags") or "بدون تگ"))}</p>'
        f'<p>📄 <b>توضیحات</b><br>{escape(str(task.get("description") or "بدون توضیحات"))}</p>'
        '<p>━━━━━━━━━━━━━━━━</p>'
        '<p><b>آیا اطلاعات مورد تأیید است؟</b></p>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="success" data="assign_confirm_create">✅ تایید و ثبت</tg-button>'
        '<tg-button type="callback_data" style="primary" data="assign_change_create">✏️ تغییر مسئول</tg-button>'
        '</tg-button-row>'
        '<tg-button-row align="center">'
        '<tg-button type="callback_data" style="link" data="assign_cancel_create">❌ لغو</tg-button>'
        '</tg-button-row>'
    )


def _success_rich_html(task_id, task):
    """Final Rich state: keep the complete task description/media visible after creation."""
    description = str(task.get("description") or "").strip()
    parts = [
        '<p><b>🎉 تسک با موفقیت ثبت شد</b></p>',
        '<p>وظیفه شما با موفقیت ایجاد و ذخیره شد.</p>',
        '<p>━━━━━━━━━━━━━━━━</p>',
        f'<p>🆔 <b>شناسه تسک</b><br><code>{escape(str(task_id))}</code></p>',
        f'<p>📝 <b>عنوان</b><br>{escape(str(task.get("title") or "—"))}</p>',
        f'<p>🎯 <b>اولویت</b><br>{escape(str({"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(task.get("priority"), "—")))}</p>',
        f'<p>📅 <b>زمان انجام</b><br>{escape(str(task.get("deadline") or "بدون زمان‌بندی"))}</p>',
        f'<p>📂 <b>دسته‌بندی</b><br>{escape(str(task.get("category") or "بدون دسته‌بندی"))}</p>',
        f'<p>🏷 <b>تگ</b><br>{escape(str(task.get("tags") or "بدون تگ"))}</p>',
        f'<p>📄 <b>توضیحات</b><br>{escape(description or "بدون توضیحات")}</p>',
    ]
    return "".join(parts)


def _description_text(context):
    values = context.user_data.get("description_text_parts") or []
    return "\n\n".join(str(value).strip() for value in values if str(value).strip())


def _extract_description_media(message):
    if message.photo:
        return {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
    if message.video:
        return {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
    if message.location:
        return {"type": "location", "latitude": message.location.latitude, "longitude": message.location.longitude}
    return None


def install_create_task_rich_progress(task_module):
    """Install presentation, cleanup, media handling, and final-state patches."""
    if getattr(task_module, "_create_task_rich_progress_installed", False):
        return
    task_module._create_task_rich_progress_installed = True

    rich_flow = sys.modules.get("handlers.create_task_flow")
    if rich_flow is None:
        import handlers.create_task_flow as rich_flow

    original_edit_rich = rich_flow._edit_rich
    original_save_task = task_module.save_task
    original_assignment = task_module.assignment_callback
    original_optional = task_module.optional_field_callback

    async def edit_rich_with_progress(context, fallback_message, html, media=None):
        summary = _draft_summary(context)
        if summary:
            html = summary + html
        media_payload = media if media is not None else _rich_media_payload(context)
        if media_payload:
            message_id = context.user_data.get("create_task_message_id")
            chat_id = getattr(fallback_message, "chat_id", None)
            if message_id and chat_id:
                await context.bot._post("editMessageText", data={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "rich_message": {"html": html, "media": media_payload, "is_rtl": True},
                })
                return True
        return await original_edit_rich(context, fallback_message, html)

    rich_flow._edit_rich = edit_rich_with_progress

    async def show_summary_rich(query, context):
        task = context.user_data.setdefault("new_task", {})
        await rich_flow._edit_rich(context, query.message, _summary_rich_html(task))

    rich_flow._show_summary = show_summary_rich

    async def save_task_with_cleanup(update, context):
        step = context.user_data.get("step")
        message = update.effective_message
        if step == "description" and message:
            media = _extract_description_media(message)
            text = str(getattr(message, "text", "") or "").strip()
            if media:
                items = context.user_data.setdefault("description_media", [])
                if len(items) >= 50:
                    return
                items.append(media)
                if media.get("caption"):
                    context.user_data.setdefault("description_text_parts", []).append(media["caption"])
            elif text:
                context.user_data.setdefault("description_text_parts", []).append(text)
            else:
                return await original_save_task(update, context)

            task = context.user_data.setdefault("new_task", {})
            task["description"] = _description_text(context)
            await rich_flow._edit_rich(
                context,
                message,
                '<p><b>📄 توضیحات تسک</b></p>'
                '<p>توضیحات، عکس، ویدیو یا موقعیت دیگری ارسال کنید.</p>'
                '<p>بعد از اتمام، دکمه «ادامه» را بزنید.</p>'
                + rich_flow._rows([
                    rich_flow._button("✅ ادامه", "description_skip", "success"),
                ])
                + rich_flow._footer(True, "step_back_tags"),
            )
            try:
                await message.delete()
            except Exception:
                pass
            return

        is_create_text_step = step in {
            "title", "deadline_custom", "category", "tags", "assignment_search",
        }
        result = await original_save_task(update, context)
        if is_create_text_step and message and context.user_data.get("step") != step:
            try:
                await message.delete()
            except Exception:
                pass
        return result

    task_module.save_task = save_task_with_cleanup
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.save_task = save_task_with_cleanup

        original_track_usage = getattr(main_module, "track_usage", None)
        if original_track_usage is not None and not getattr(main_module, "_create_task_media_track_installed", False):
            main_module._create_task_media_track_installed = True

            async def track_usage_with_create_media(update, context):
                await original_track_usage(update, context)
                message = update.effective_message
                if context.user_data.get("step") != "description" or not message:
                    return
                if message.photo or message.video or message.location:
                    await task_module.save_task(update, context)

            main_module.track_usage = track_usage_with_create_media

    async def optional_with_media_description(update, context):
        query = update.callback_query
        if (query.data or "") != "description_skip":
            return await original_optional(update, context)
        await query.answer()
        task = context.user_data.setdefault("new_task", {})
        task["description"] = _description_text(context)
        await rich_flow._show_assignment(query.message, context)

    task_module.optional_field_callback = optional_with_media_description
    if main_module is not None:
        main_module.optional_field_callback = optional_with_media_description

    async def assignment_with_rich_final_state(update, context):
        query = update.callback_query
        data = query.data or ""
        if data != "assign_confirm_create":
            return await original_assignment(update, context)

        await query.answer()
        task = context.user_data.get("new_task") or {}
        if not isinstance(task, dict):
            await rich_flow._edit_rich(context, query.message, '<p><b>⚠️ اطلاعات ایجاد تسک پیدا نشد.</b></p>')
            return

        error = rich_flow.validate_create_task_draft(task)
        if error:
            await rich_flow._edit_rich(context, query.message, f'<p><b>⚠️ {escape(error)}</b></p>')
            return

        uid = update.effective_user.id
        task_id = await task_module._finalize_task(uid, task)

        try:
            from services.task_media import save_task_media_async
            await save_task_media_async(task_id, _description_media(context))
        except Exception:
            pass

        assignee = task.get("assignee")
        saved = None
        try:
            saved = await task_module.get_task_by_id_async(task_id)
        except Exception:
            pass

        # Do not call the progress-summary wrapper here: the final message must
        # render the actual task data and its attachments, not only a transient draft.
        final_html = _success_rich_html(task_id, task)
        media_payload = _rich_media_payload(context)
        if media_payload:
            await context.bot._post("editMessageText", data={
                "chat_id": query.message.chat_id,
                "message_id": context.user_data.get("create_task_message_id"),
                "rich_message": {
                    "html": final_html,
                    "media": media_payload,
                    "is_rtl": True,
                },
            })
        else:
            await rich_flow._edit_rich(context, query.message, final_html)

        if _description_media_html(context):
            # Rich media is already part of the final message. Text captions and
            # the textual description are retained in final_html above.
            pass

        if assignee:
            try:
                await task_module._notify_assignment(context, saved or task, assignee, update.effective_user)
            except Exception:
                pass

        context.user_data.clear()

    task_module.assignment_callback = assignment_with_rich_final_state
    if main_module is not None:
        main_module.assignment_callback = assignment_with_rich_final_state
