"""Per-bot task capability enforcement.

This module keeps task-flow customization out of handlers/task.py. Each bot
profile can selectively enable/disable task capabilities through
settings.task_options without creating bot-specific branches in the task
handler.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


DEFAULT_TASK_OPTIONS: dict[str, bool] = {
    "allow_assignment": True,
    "allow_tags": True,
    "allow_comments": True,
    "allow_categories": True,
    "allow_search": True,
    "allow_templates": True,
    "allow_bulk_import": True,
    "allow_ai_task_creation": True,
}


def task_options(profile: Any) -> dict[str, bool]:
    """Return normalized task options for a bot profile."""
    result = DEFAULT_TASK_OPTIONS.copy()
    if profile is not None:
        result.update({k: bool(v) for k, v in (profile.settings.get("task_options", {}) or {}).items() if k in result})
    return result


def task_option_enabled(context: Any, name: str) -> bool:
    profile = context.bot_data.get("bot_config") if context is not None else None
    return task_options(profile).get(name, True)


async def _show_no_assignment_confirmation(update, context) -> None:
    """Show the task confirmation UI without exposing assignment controls."""
    task = context.user_data.get("new_task") or {}
    task["assignee"] = None
    if not task_option_enabled(context, "allow_tags"):
        task["tags"] = ""
    context.user_data["new_task"] = task
    context.user_data["step"] = "task_confirm_create"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تایید و ثبت", callback_data="task_confirm_create")],
            [InlineKeyboardButton("❌ لغو", callback_data="task_cancel_create")],
        ]
    )
    task_handler = __import__("handlers.task", fromlist=["_assignment_summary"])
    summary = task_handler._assignment_summary(task).replace("👤 مسئول:\n❌ تعیین نشده\n\n", "")
    await update.effective_message.reply_text(summary, reply_markup=keyboard)


async def _finalize_without_assignment(update, context) -> None:
    task_handler = __import__("handlers.task", fromlist=["_finalize_task"])
    task = context.user_data.get("new_task") or {}
    task["assignee"] = None
    if not task_option_enabled(context, "allow_tags"):
        task["tags"] = ""
    task_id = await task_handler._finalize_task(update.effective_user.id, task)
    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")


def wrap_save_task(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Make the existing text flow skip disabled optional task stages."""
    @wraps(original)
    async def wrapper(update, context):
        step = context.user_data.get("step")
        task = context.user_data.get("new_task")
        if not task:
            return await original(update, context)

        if step == "category" and not task_option_enabled(context, "allow_categories"):
            task["category"] = ""
            if task_option_enabled(context, "allow_tags"):
                task_handler = __import__("handlers.task", fromlist=["_ask_tags"])
                await task_handler._ask_tags(update.message, context)
            else:
                task_handler = __import__("handlers.task", fromlist=["_ask_description"])
                await task_handler._ask_description(update.message, context)
            return

        if step == "category" and not task_option_enabled(context, "allow_tags"):
            task["category"] = update.message.text or ""
            task["tags"] = ""
            task_handler = __import__("handlers.task", fromlist=["_ask_description"])
            await task_handler._ask_description(update.message, context)
            return

        if step == "tags" and not task_option_enabled(context, "allow_tags"):
            task["tags"] = ""
            task_handler = __import__("handlers.task", fromlist=["_ask_description"])
            await task_handler._ask_description(update.message, context)
            return

        if step == "description" and not task_option_enabled(context, "allow_assignment"):
            task["description"] = update.message.text or ""
            await _show_no_assignment_confirmation(update, context)
            return

        return await original(update, context)

    return wrapper


def wrap_optional_field_callback(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def wrapper(update, context):
        data = update.callback_query.data or ""
        task = context.user_data.get("new_task") or {}
        if data.startswith("category_") and not task_option_enabled(context, "allow_categories"):
            task["category"] = ""
            context.user_data["new_task"] = task
            if task_option_enabled(context, "allow_tags"):
                handler = __import__("handlers.task", fromlist=["_ask_tags"])
                await handler._ask_tags(update.callback_query.message, context)
            else:
                handler = __import__("handlers.task", fromlist=["_ask_description"])
                await handler._ask_description(update.callback_query.message, context)
            await update.callback_query.answer()
            return
        if data.startswith("tags_") and not task_option_enabled(context, "allow_tags"):
            task["tags"] = ""
            context.user_data["new_task"] = task
            handler = __import__("handlers.task", fromlist=["_ask_description"])
            await handler._ask_description(update.callback_query.message, context)
            await update.callback_query.answer()
            return
        if data == "description_skip" and not task_option_enabled(context, "allow_assignment"):
            task["description"] = ""
            context.user_data["new_task"] = task
            await update.callback_query.answer()
            await _show_no_assignment_confirmation(update, context)
            return
        return await original(update, context)

    return wrapper


def wrap_button_handler(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def wrapper(update, context):
        data = (update.callback_query.data or "") if update.callback_query else ""

        if data == "task_confirm_create" and not task_option_enabled(context, "allow_assignment"):
            await update.callback_query.answer()
            await _finalize_without_assignment(update, context)
            return
        if data == "task_cancel_create" and not task_option_enabled(context, "allow_assignment"):
            await update.callback_query.answer()
            context.user_data.clear()
            await update.callback_query.message.reply_text("❌ ایجاد تسک لغو شد.")
            return

        if data.startswith("assign_") and not task_option_enabled(context, "allow_assignment"):
            await update.callback_query.answer("تخصیص مسئول برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith("comment_") and not task_option_enabled(context, "allow_comments"):
            await update.callback_query.answer("کامنت برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith("tags_") and not task_option_enabled(context, "allow_tags"):
            await update.callback_query.answer("تگ برای این ربات فعال نیست.", show_alert=True)
            return
        return await original(update, context)

    return wrapper


def wrap_deadline_selected(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def wrapper(update, context):
        if task_option_enabled(context, "allow_categories"):
            return await original(update, context)

        query = update.callback_query
        await query.answer()
        value = query.data.replace("deadline_", "")
        task = context.user_data.setdefault("new_task", {})
        if value == "custom":
            context.user_data["step"] = "deadline_custom"
            await query.message.reply_text("📅 تاریخ دقیق را وارد کنید:\n• میلادی: `2026-08-20`\n• شمسی: `1405-05-29`", parse_mode="Markdown")
            return
        if value == "none":
            task["deadline"] = ""
        else:
            from datetime import datetime, timedelta
            task["deadline"] = (datetime.now() + timedelta(days=int(value))).strftime("%Y-%m-%d")

        task["category"] = ""
        if task_option_enabled(context, "allow_tags"):
            handler = __import__("handlers.task", fromlist=["_ask_tags"])
            await handler._ask_tags(query.message, context)
        else:
            handler = __import__("handlers.task", fromlist=["_ask_description"])
            await handler._ask_description(query.message, context)

    return wrapper


def install_task_capabilities(app) -> None:
    """Wrap already-registered task handlers without changing core handlers."""
    targets = {
        "save_task": wrap_save_task,
        "optional_field_callback": wrap_optional_field_callback,
        "button_handler": wrap_button_handler,
        "deadline_selected": wrap_deadline_selected,
    }
    for handlers in app.handlers.values():
        for handler in handlers:
            callback = getattr(handler, "callback", None)
            name = getattr(callback, "__name__", "")
            wrapper_factory = targets.get(name)
            if wrapper_factory and not getattr(callback, "_task_capability_wrapped", False):
                wrapped = wrapper_factory(callback)
                setattr(wrapped, "_task_capability_wrapped", True)
                handler.callback = wrapped
