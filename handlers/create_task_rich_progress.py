"""Progress and final-state presentation for the manual Rich create-task flow.

Keeps the user's input messages out of the chat and renders the accumulated
create-task draft, final confirmation, and success state inside the same
Telegram Rich Message.
"""

from html import escape
import sys


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
        labels.append(f"📄 <b>توضیحات:</b> {escape(description[:300])}")

    if isinstance(assignee, dict):
        name = assignee.get("display_name") or assignee.get("username") or assignee.get("user_id")
        if name:
            labels.append(f"👤 <b>مسئول:</b> {escape(str(name))}")
    elif assignee is None and "assignee" in task:
        labels.append("👤 <b>مسئول:</b> بدون مسئول")

    if not labels:
        return ""
    return '<p><b>📋 اطلاعات ثبت‌شده</b></p>' + "".join(f"<p>{line}</p>" for line in labels) + "<p>━━━━━━━━━━━━</p>"


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
        f'<p>👤 <b>مسئول</b><br>{escape(str(name))}</p>'
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


def _success_rich_html(task_id):
    return (
        '<p><b>🎉 تسک با موفقیت ثبت شد</b></p>'
        '<p>وظیفه شما با موفقیت ایجاد و ذخیره شد.</p>'
        '<p>━━━━━━━━━━━━━━━━</p>'
        f'<p>🆔 <b>شناسه تسک</b><br><code>{escape(str(task_id))}</code></p>'
        '<p>💡 از این شناسه می‌توانید برای مشاهده یا پیگیری تسک استفاده کنید.</p>'
    )


def install_create_task_rich_progress(task_module):
    """Install presentation, cleanup, and final-state patches after Rich flow."""
    if getattr(task_module, "_create_task_rich_progress_installed", False):
        return
    task_module._create_task_rich_progress_installed = True

    # The Rich implementation lives in create_task_flow, while task_module
    # is handlers.task. Patch the actual Rich module so its global calls are
    # also covered by the progress presentation.
    rich_flow = sys.modules.get("handlers.create_task_flow")
    if rich_flow is None:
        import handlers.create_task_flow as rich_flow

    original_edit_rich = rich_flow._edit_rich
    original_save_task = task_module.save_task
    original_assignment = task_module.assignment_callback

    async def edit_rich_with_progress(context, fallback_message, html):
        summary = _draft_summary(context)
        if summary:
            html = summary + html
        return await original_edit_rich(context, fallback_message, html)

    rich_flow._edit_rich = edit_rich_with_progress

    async def save_task_with_cleanup(update, context):
        step = context.user_data.get("step")
        message = update.effective_message
        is_create_text_step = step in {
            "title", "deadline_custom", "category", "tags", "description",
            "assignment_search",
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
        assignee = task.get("assignee")

        saved = None
        try:
            saved = await task_module.get_task_by_id_async(task_id)
        except Exception:
            pass

        # Replace the summary in-place with the final Rich success state.
        # No second "task created" message is sent.
        await rich_flow._edit_rich(context, query.message, _success_rich_html(task_id))

        if assignee:
            try:
                await task_module._notify_assignment(context, saved or task, assignee, update.effective_user)
            except Exception:
                pass

        context.user_data.clear()

    task_module.assignment_callback = assignment_with_rich_final_state
    if main_module is not None:
        main_module.assignment_callback = assignment_with_rich_final_state
