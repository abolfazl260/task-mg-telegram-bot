"""Progress, attachments and cleanup for the one-message Rich create-task flow."""

from html import escape
import logging
import sys

logger = logging.getLogger(__name__)


def _description_media(context):
    items = context.user_data.get("description_media") or []
    return items if isinstance(items, list) else []


def _rich_media_payload(context):
    """Build Telegram Bot API InputRichMessageMedia entries.

    Rich HTML can reference previously received Telegram files through tg://
    links. The media object itself carries the original file_id, so no local
    download/upload is necessary.
    """
    payload = []
    for index, item in enumerate(_description_media(context)):
        kind = item.get("type")
        file_id = item.get("file_id")
        if not file_id:
            continue
        if kind == "photo":
            uri_kind = "photo"
            media_type = "photo"
        elif kind == "video":
            uri_kind = "video"
            media_type = "video"
        elif kind == "document":
            uri_kind = "document"
            media_type = "document"
        elif kind == "audio":
            uri_kind = "audio"
            media_type = "audio"
        elif kind == "voice":
            # Bot API exposes voice-note input media; tg://audio is the Rich
            # Message reference supported by the API for audio-like media.
            uri_kind = "audio"
            media_type = "voice_note"
        elif kind == "animation":
            uri_kind = "video"
            media_type = "animation"
        else:
            continue
        payload.append({
            "id": f"desc_media_{index}",
            "media": {"type": media_type, "media": file_id},
            "_uri_kind": uri_kind,
        })
    return payload


def _clean_media_payload(payload):
    return [{k: v for k, v in item.items() if k != "_uri_kind"} for item in payload]


def _media_uri(index, item):
    kind = item.get("type")
    uri_kind = {
        "photo": "photo",
        "video": "video",
        "document": "document",
        "audio": "audio",
        "voice": "audio",
        "animation": "video",
    }.get(kind)
    if not uri_kind:
        return None
    return f"tg://{uri_kind}?id=desc_media_{index}"


def _description_media_html(context):
    blocks = []
    for index, item in enumerate(_description_media(context)):
        kind = item.get("type")
        uri = _media_uri(index, item)
        if uri:
            if kind in {"photo"}:
                blocks.append(f'<img src="{uri}"/>')
            elif kind in {"video", "animation"}:
                blocks.append(f'<video src="{uri}"></video>')
            elif kind in {"audio", "voice"}:
                blocks.append(f'<audio src="{uri}"></audio>')
            elif kind == "document":
                blocks.append(f'<a href="{uri}">📎 فایل پیوست‌شده</a>')
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
                logger.warning("Invalid description location: %r", item)
    if not blocks:
        return ""
    return '<p><b>📎 پیوست‌های توضیحات</b></p>' + "".join(blocks)


def _description_text(context):
    values = context.user_data.get("description_text_parts") or []
    return "\n\n".join(str(value).strip() for value in values if str(value).strip())


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
    description = str(task.get("description") or _description_text(context) or "").strip()
    assignee = task.get("assignee")
    if title: labels.append(f"📝 <b>عنوان:</b> {escape(title)}")
    if priority: labels.append(f"🎯 <b>اولویت:</b> {escape(priority)}")
    if deadline: labels.append(f"📅 <b>زمان:</b> {escape(deadline)}")
    if category: labels.append(f"📂 <b>دسته‌بندی:</b> {escape(category)}")
    if tags: labels.append(f"🏷 <b>تگ:</b> {escape(tags)}")
    if description: labels.append(f"📄 <b>توضیحات:</b> {escape(description[:1500])}")
    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or assignee.get("user_id")
        if name: labels.append(f"👤 <b>مسئول:</b> {escape(str(name))}")
    elif assignee is None and "assignee" in task:
        labels.append("👤 <b>مسئول:</b> بدون مسئول")
    media_html = _description_media_html(context)
    if not labels and not media_html:
        return ""
    text = '<p><b>📋 اطلاعات ثبت‌شده</b></p>' + "".join(f"<p>{line}</p>" for line in labels)
    if media_html: text += media_html
    return text + "<p>━━━━━━━━━━━━</p>"


def _summary_rich_html(task, context):
    assignee = task.get("assignee")
    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or str(assignee.get("user_id") or "کاربر")
    else:
        name = "بدون مسئول"
    priority = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}.get(task.get("priority"), "—")
    description = str(task.get("description") or _description_text(context) or "").strip()
    return (
        '<p><b>📋 خلاصه وظیفه</b></p>'
        '<p>اطلاعات زیر را قبل از ثبت بررسی کنید:</p>'
        '<p>━━━━━━━━━━━━━━━━</p>'
        f'<p>📝 <b>عنوان</b><br>{escape(str(task.get("title") or "—"))}</p>'
        f'<p>🎯 <b>اولویت</b><br>{escape(priority)}</p>'
        f'<p>📅 <b>زمان انجام</b><br>{escape(str(task.get("deadline") or "بدون زمان‌بندی"))}</p>'
        f'<p>📂 <b>دسته‌بندی</b><br>{escape(str(task.get("category") or "بدون دسته‌بندی"))}</p>'
        f'<p>🏷 <b>تگ</b><br>{escape(str(task.get("tags") or "بدون تگ"))}</p>'
        f'<p>📄 <b>توضیحات</b><br>{escape(description or "بدون توضیحات")}</p>'
        + _description_media_html(context)
        + '<p>👤 <b>مسئول:</b> ' + escape(str(name)) + '</p>'
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


def _success_rich_html(task_id, task, context):
    description = str(task.get("description") or _description_text(context) or "").strip()
    return (
        '<p><b>🎉 تسک با موفقیت ثبت شد</b></p>'
        '<p>وظیفه شما با موفقیت ایجاد و ذخیره شد.</p>'
        '<p>━━━━━━━━━━━━━━━━</p>'
        f'<p>🆔 <b>شناسه تسک</b><br><code>{escape(str(task_id))}</code></p>'
        f'<p>📝 <b>عنوان</b><br>{escape(str(task.get("title") or "—"))}</p>'
        f'<p>🎯 <b>اولویت</b><br>{escape(str({"high": "بالا", "medium": "متوسط", "low": "پایین"}.get(task.get("priority"), "—")))}</p>'
        f'<p>📅 <b>زمان انجام</b><br>{escape(str(task.get("deadline") or "بدون زمان‌بندی"))}</p>'
        f'<p>📂 <b>دسته‌بندی</b><br>{escape(str(task.get("category") or "بدون دسته‌بندی"))}</p>'
        f'<p>🏷 <b>تگ</b><br>{escape(str(task.get("tags") or "بدون تگ"))}</p>'
        f'<p>📄 <b>توضیحات</b><br>{escape(description or "بدون توضیحات")}</p>'
        + _description_media_html(context)
    )


def _extract_description_media(message):
    if message.photo:
        return {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
    if message.video:
        return {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
    if message.document:
        return {"type": "document", "file_id": message.document.file_id, "file_name": message.document.file_name or "", "caption": message.caption or ""}
    if message.audio:
        return {"type": "audio", "file_id": message.audio.file_id, "file_name": message.audio.file_name or "", "caption": message.caption or ""}
    if message.voice:
        return {"type": "voice", "file_id": message.voice.file_id, "caption": message.caption or ""}
    if message.animation:
        return {"type": "animation", "file_id": message.animation.file_id, "file_name": message.animation.file_name or "", "caption": message.caption or ""}
    if message.location:
        return {"type": "location", "latitude": message.location.latitude, "longitude": message.location.longitude}
    return None


def _is_description_attachment(message):
    return bool(message and (
        message.photo or message.video or message.document or message.audio or
        message.voice or message.animation or message.location
    ))


async def _delete_user_message(message):
    """Delete only after the Rich edit succeeded.

    Telegram clients render their native Thanos/vaporize animation when a
    message is deleted. There is no separate Bot API flag required for it.
    """
    if not message:
        return False
    try:
        await message.delete()
        return True
    except Exception:
        try:
            await message.get_bot().delete_message(message.chat_id, message.message_id)
            return True
        except Exception:
            logger.exception("Failed to delete accepted create-task input message")
            return False


async def _edit_progress(context, fallback_message, html):
    rich_flow = sys.modules["handlers.create_task_flow"]
    summary = _draft_summary(context)
    if summary:
        html = summary + html
    payload = _rich_media_payload(context)
    data = {
        "chat_id": fallback_message.chat_id,
        "message_id": context.user_data.get("create_task_message_id"),
        "rich_message": {"html": html, "is_rtl": True},
    }
    if payload:
        data["rich_message"]["media"] = _clean_media_payload(payload)
    if data["message_id"]:
        await context.bot._post("editMessageText", data=data)
        return True
    return await rich_flow._edit_rich(context, fallback_message, html)


def install_create_task_rich_progress(task_module):
    if getattr(task_module, "_create_task_rich_progress_installed", False):
        return
    task_module._create_task_rich_progress_installed = True
    rich_flow = sys.modules.get("handlers.create_task_flow")
    if rich_flow is None:
        import handlers.create_task_flow as rich_flow

    original_save_task = task_module.save_task
    original_assignment = task_module.assignment_callback
    original_optional = task_module.optional_field_callback

    async def show_summary_rich(query, context):
        task = context.user_data.setdefault("new_task", {})
        if not task.get("description"):
            task["description"] = _description_text(context)
        await _edit_progress(context, query.message, _summary_rich_html(task, context))

    rich_flow._show_summary = show_summary_rich

    async def save_task_with_progress(update, context):
        step = context.user_data.get("step")
        message = update.effective_message
        if step == "description" and message:
            media = _extract_description_media(message)
            text = str(getattr(message, "text", "") or "").strip()
            if media:
                items = context.user_data.setdefault("description_media", [])
                if len(items) >= 50:
                    logger.warning("Rich create-task media limit reached user_id=%s", getattr(update.effective_user, "id", None))
                    return
                items.append(media)
                caption = str(media.get("caption") or "").strip()
                if caption:
                    context.user_data.setdefault("description_text_parts", []).append(caption)
            elif text:
                context.user_data.setdefault("description_text_parts", []).append(text)
            else:
                return await original_save_task(update, context)

            task = context.user_data.setdefault("new_task", {})
            task["description"] = _description_text(context)
            # The deletion happens only after this await returns successfully.
            await _edit_progress(
                context,
                message,
                '<p><b>📄 توضیحات تسک</b></p>'
                '<p>توضیحات، عکس، ویدیو، فایل، موسیقی، صدا یا موقعیت دیگری ارسال کنید.</p>'
                '<p>هر مورد جدید به همین پیش‌نویس اضافه می‌شود.</p>'
                '<p>بعد از اتمام، دکمه «ادامه» را بزنید.</p>'
                + rich_flow._rows([rich_flow._button("✅ ادامه", "description_skip", "success")])
                + rich_flow._footer(True, "step_back_tags"),
            )
            await _delete_user_message(message)
            return

        is_create_text_step = step in {"title", "deadline_custom", "category", "tags", "assignment_search"}
        result = await original_save_task(update, context)
        if is_create_text_step and message and context.user_data.get("step") != step:
            await _delete_user_message(message)
        return result

    task_module.save_task = save_task_with_progress
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.save_task = save_task_with_progress
        original_track_usage = getattr(main_module, "track_usage", None)
        if original_track_usage is not None and not getattr(main_module, "_create_task_media_track_installed", False):
            main_module._create_task_media_track_installed = True

            async def track_usage_with_create_media(update, context):
                await original_track_usage(update, context)
                if context.user_data.get("step") != "description":
                    return
                message = update.effective_message
                if not _is_description_attachment(message):
                    return
                try:
                    await task_module.save_task(update, context)
                except Exception:
                    logger.exception("Failed to process create-task attachment")

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
        if (query.data or "") != "assign_confirm_create":
            return await original_assignment(update, context)
        await query.answer()
        task = context.user_data.get("new_task") or {}
        if not isinstance(task, dict):
            await rich_flow._edit_rich(context, query.message, '<p><b>⚠️ اطلاعات ایجاد تسک پیدا نشد.</b></p>')
            return
        if not task.get("description"):
            task["description"] = _description_text(context)
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
            logger.exception("Failed to persist task attachments task_id=%s", task_id)

        assignee = task.get("assignee")
        saved = None
        try:
            saved = await task_module.get_task_by_id_async(task_id)
        except Exception:
            pass

        final_html = _success_rich_html(task_id, task, context)
        payload = _rich_media_payload(context)
        data = {
            "chat_id": query.message.chat_id,
            "message_id": context.user_data.get("create_task_message_id"),
            "rich_message": {"html": final_html, "is_rtl": True},
        }
        if payload:
            data["rich_message"]["media"] = _clean_media_payload(payload)
        await context.bot._post("editMessageText", data=data)

        if assignee:
            try:
                await task_module._notify_assignment(context, saved or task, assignee, update.effective_user)
            except Exception:
                logger.exception("Failed to notify assignee task_id=%s", task_id)
        context.user_data.clear()

    task_module.assignment_callback = assignment_with_rich_final_state
    if main_module is not None:
        main_module.assignment_callback = assignment_with_rich_final_state
        # Critical: main imported safe_assignment_confirm directly. Point that
        # already-registered callback at the same Rich finalizer.
        main_module.safe_assignment_confirm = assignment_with_rich_final_state
