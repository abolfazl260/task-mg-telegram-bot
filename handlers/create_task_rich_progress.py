"""Progress presentation overlay for the manual Rich create-task flow.

Keeps the user's input messages out of the chat and renders the accumulated
create-task draft at the top of the same Rich Message after every step.
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


def install_create_task_rich_progress(task_module):
    """Install the progress layer after the main Rich create-flow patch."""
    if getattr(task_module, "_create_task_rich_progress_installed", False):
        return
    task_module._create_task_rich_progress_installed = True

    # The Rich implementation lives in create_task_flow, while task_module
    # is handlers.task. Patch the actual Rich module so its own global
    # _edit_rich calls receive the accumulated draft.
    rich_flow = sys.modules.get("handlers.create_task_flow")
    if rich_flow is None:
        import handlers.create_task_flow as rich_flow

    original_edit_rich = rich_flow._edit_rich
    original_save_task = task_module.save_task

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

        # Delete only accepted create-flow text inputs. Invalid input remains
        # visible so the user can see what needs correction.
        if is_create_text_step and message and context.user_data.get("step") != step:
            try:
                await message.delete()
            except Exception:
                pass
        return result

    # Keep all references that may have been captured by the application in
    # sync. Non-create-task flows continue to use the same wrapped handler.
    task_module.save_task = save_task_with_cleanup
    main_module = sys.modules.get("main")
    if main_module is not None:
        main_module.save_task = save_task_with_cleanup

    # Make the wrapper idempotent if installation is attempted again.
    rich_flow._rich_progress_edit_original = original_edit_rich
