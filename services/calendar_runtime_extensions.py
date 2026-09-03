"""Small runtime extensions that need the current Telegram viewer context."""

from contextvars import ContextVar
from datetime import timedelta

from services.date_service import get_user_date_format_for_display
from services.timezone_service import get_current_local_datetime_async
from services.user_service import get_user_date_format_async
from utils.date_parse import deadline_input_hint
from services import calendar_runtime

_current_user_id = ContextVar("calendar_current_user_id", default=None)


def set_current_user(user_id):
    _current_user_id.set(user_id)


def viewer_id(task=None):
    current = _current_user_id.get()
    if current is not None:
        return current
    value = (task or {}).get("user_id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def format_task_card(task):
    """Async adapter for task.py, which awaits the task-card formatter."""
    return calendar_runtime.format_task_card(task, viewer_id(task))


def build_full_report(tasks):
    return calendar_runtime.build_full_report(tasks, viewer_id(tasks[0] if tasks else None))


async def deadline_hint_for_user(user_id):
    return deadline_input_hint(await get_user_date_format_async(user_id))


async def deadline_selected(update, context):
    query = update.callback_query
    await query.answer()
    value = query.data.replace("deadline_", "")
    user_id = update.effective_user.id

    if value == "custom":
        context.user_data["step"] = "deadline_custom"
        hint = await deadline_hint_for_user(user_id)
        await query.message.reply_text(
            "📅 تاریخ دقیق را وارد کنید:\n"
            f"{hint}\n\n"
            "برای سازگاری، تاریخ با تقویم دیگر نیز پذیرفته می‌شود.",
            parse_mode="Markdown",
        )
        return

    if value == "none":
        context.user_data["new_task"]["deadline"] = ""
        context.user_data["step"] = "category"
        from handlers.task import _ask_category
        await _ask_category(query.message, context, user_id)
        return

    try:
        days = int(value)
    except ValueError:
        await query.message.reply_text("⚠️ گزینه زمان‌بندی نامعتبر است.")
        return

    _, now = await get_current_local_datetime_async(user_id)
    deadline = now.date() + timedelta(days=days)
    context.user_data["new_task"]["deadline"] = deadline.isoformat()
    context.user_data["step"] = "category"
    from handlers.task import _ask_category
    await _ask_category(query.message, context, user_id)
