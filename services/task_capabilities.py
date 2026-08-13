"""Per-bot task capability enforcement.

Task customization is profile-driven. The same handlers are shared by all
bots, while the active BotProfile decides which task capabilities are allowed.
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

_WRAPPABLE_CALLBACKS = {
    "assignment_callback",
    "assignment_manage_callback",
    "take_assignment",
    "take_confirm",
    "safe_assignment_confirm",
    "comment_callback",
    "comment_cancel_callback",
    "button_handler",
}


def task_options(profile: Any) -> dict[str, bool]:
    result = DEFAULT_TASK_OPTIONS.copy()
    if profile is not None:
        raw = (getattr(profile, "settings", {}) or {}).get("task_options", {}) or {}
        result.update({k: bool(v) for k, v in raw.items() if k in result})
    return result


def task_option_enabled(context: Any, name: str) -> bool:
    profile = context.bot_data.get("bot_config") if context is not None else None
    return task_options(profile).get(name, True)


async def _show_no_assignment_confirmation(update, context) -> None:
    task = context.user_data.get("new_task") or {}
    task["assignee"] = None
    task["team_id"] = ""
    if not task_option_enabled(context, "allow_tags"):
        task["tags"] = ""
    context.user_data["new_task"] = task
    context.user_data["step"] = "task_confirm_create"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و ثبت", callback_data="task_confirm_create")],
        [InlineKeyboardButton("❌ لغو", callback_data="task_cancel_create")],
    ])
    handler = __import__("handlers.task", fromlist=["_assignment_summary"])
    summary = handler._assignment_summary(task).replace("👤 مسئول:\n❌ تعیین نشده\n\n", "")
    await update.effective_message.reply_text(summary, reply_markup=keyboard)


async def _finalize_without_assignment(update, context) -> None:
    handler = __import__("handlers.task", fromlist=["_finalize_task"])
    task = context.user_data.get("new_task") or {}
    task["assignee"] = None
    task["team_id"] = ""
    if not task_option_enabled(context, "allow_tags"):
        task["tags"] = ""
    task_id = await handler._finalize_task(update.effective_user.id, task)
    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")


def wrap_save_task(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def wrapper(update, context):
        step = context.user_data.get("step")
        task = context.user_data.get("new_task")
        if not task:
            return await original(update, context)
        if step == "category":
            task["category"] = (update.message.text or "") if task_option_enabled(context, "allow_categories") else ""
            if task_option_enabled(context, "allow_tags"):
                handler = __import__("handlers.task", fromlist=["_ask_tags"])
                await handler._ask_tags(update.message, context)
            else:
                task["tags"] = ""
                handler = __import__("handlers.task", fromlist=["_ask_description"])
                await handler._ask_description(update.message, context)
            return
        if step == "tags" and not task_option_enabled(context, "allow_tags"):
            task["tags"] = ""
            handler = __import__("handlers.task", fromlist=["_ask_description"])
            await handler._ask_description(update.message, context)
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
        if data.startswith("category_"):
            if not task_option_enabled(context, "allow_categories"):
                task["category"] = ""
            elif data.startswith("category_pick_"):
                selected = data.replace("category_pick_", "", 1)
                categories = [
                    (t.get("category") or "").strip()
                    for t in await __import__("services.task_service", fromlist=["get_active_tasks_async"]).get_active_tasks_async(update.effective_user.id)
                    if (t.get("category") or "").strip()
                ]
                task["category"] = next((c for c in categories if c[:40] == selected), selected)
            else:
                task["category"] = ""
            context.user_data["new_task"] = task
            if task_option_enabled(context, "allow_tags"):
                handler = __import__("handlers.task", fromlist=["_ask_tags"])
                await handler._ask_tags(update.callback_query.message, context)
            else:
                task["tags"] = ""
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


def _sanitize_ai_draft(context, draft: dict) -> dict:
    if not task_option_enabled(context, "allow_tags"):
        draft["tags"] = ""
    if not task_option_enabled(context, "allow_categories"):
        draft["category"] = ""
    if not task_option_enabled(context, "allow_assignment"):
        draft["assignee"] = None
        draft["team_id"] = ""
    return draft


def wrap_callback(original: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(original)
    async def wrapper(update, context):
        data = (update.callback_query.data or "") if update.callback_query else ""
        if data.startswith("ai_task_"):
            if not task_option_enabled(context, "allow_ai_task_creation"):
                await update.callback_query.answer("ایجاد تسک با هوش مصنوعی برای این ربات فعال نیست.", show_alert=True)
                return
            draft = context.user_data.get("ai_request_draft")
            if isinstance(draft, dict):
                _sanitize_ai_draft(context, draft)
        if data in {"task_confirm_create", "task_cancel_create"} and not task_option_enabled(context, "allow_assignment"):
            await update.callback_query.answer()
            if data == "task_confirm_create":
                await _finalize_without_assignment(update, context)
            else:
                context.user_data.clear()
                await update.callback_query.message.reply_text("❌ ایجاد تسک لغو شد.")
            return
        if data.startswith(("assign_", "owner_", "take_", "asg_", "chg_")) and not task_option_enabled(context, "allow_assignment"):
            await update.callback_query.answer("تخصیص مسئول برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith("comment_") and not task_option_enabled(context, "allow_comments"):
            await update.callback_query.answer("کامنت برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith(("tag_", "tags_", "step_back_tags")) and not task_option_enabled(context, "allow_tags"):
            await update.callback_query.answer("تگ برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith("template_") and not task_option_enabled(context, "allow_templates"):
            await update.callback_query.answer("تمپلیت برای این ربات فعال نیست.", show_alert=True)
            return
        if data.startswith("import_") and not task_option_enabled(context, "allow_bulk_import"):
            await update.callback_query.answer("ثبت گروهی برای این ربات فعال نیست.", show_alert=True)
            return
        return await original(update, context)
    return wrapper


def install_task_capabilities(app: Any) -> None:
    """Wrap registered callbacks once, after the application is fully built.

    Real ``Application`` instances expose the supported ``bot_data`` mapping.
    Lightweight test doubles may not, so installation state is stored on the
    application object itself when that mapping is unavailable.
    """
    state = getattr(app, "bot_data", None)
    if state is None:
        if getattr(app, "_task_capabilities_installed", False):
            return
        for handlers in app.handlers.values():
            for handler in handlers:
                callback = getattr(handler, "callback", None)
                name = getattr(callback, "__name__", "")
                if name not in _WRAPPABLE_CALLBACKS:
                    continue
                if getattr(callback, "_task_capability_wrapped", False):
                    continue
                wrapped = wrap_callback(callback)
                setattr(wrapped, "_task_capability_wrapped", True)
                handler.callback = wrapped
        setattr(app, "_task_capabilities_installed", True)
        return

    if state.get("_task_capabilities_installed", False):
        return
    for handlers in app.handlers.values():
        for handler in handlers:
            callback = getattr(handler, "callback", None)
            name = getattr(callback, "__name__", "")
            if name not in _WRAPPABLE_CALLBACKS:
                continue
            if getattr(callback, "_task_capability_wrapped", False):
                continue
            wrapped = wrap_callback(callback)
            setattr(wrapped, "_task_capability_wrapped", True)
            handler.callback = wrapped
    state["_task_capabilities_installed"] = True
