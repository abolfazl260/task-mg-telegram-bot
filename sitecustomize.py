"""Runtime compatibility helpers for the Telegram bot.

This module keeps the production task flow intact. The only task-specific
compatibility layer is the short callback id used by category buttons; the
normal tag-suggestion installer is deliberately allowed to run first.
"""
import asyncio
import builtins
import sys
from functools import wraps

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Keep Telegram command ordering stable and always expose /start.
try:
    from telegram import Bot, BotCommand
    _original_set_my_commands = Bot.set_my_commands
    if not getattr(_original_set_my_commands, "_taskmg_ordered", False):
        _command_priority = {"ai": 0, "start": 1, "add": 2, "reports": 3}

        @wraps(_original_set_my_commands)
        async def _ordered_set_my_commands(self, commands, *args, **kwargs):
            commands = [c for c in list(commands) if c.command != "templates"]
            if not any(c.command == "start" for c in commands):
                commands.append(BotCommand("start", "شروع ربات و منوی اصلی"))
            indexed = list(enumerate(commands))
            indexed.sort(key=lambda item: (_command_priority.get(item[1].command, 1000), item[0]))
            return await _original_set_my_commands(self, [c for _, c in indexed], *args, **kwargs)

        _ordered_set_my_commands._taskmg_ordered = True
        Bot.set_my_commands = _ordered_set_my_commands
except Exception:
    pass


def _install_safe_category_flow(task_handler):
    """Install only the category adapter, without replacing tag handling."""
    if getattr(task_handler, "_safe_category_flow_installed", False):
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    async def _category_options(user_id, limit=10):
        categories = []
        seen = set()
        for task in await task_handler.get_active_tasks_async(user_id):
            category = str(task.get("category") or "").strip()
            key = category.casefold()
            if category and key not in seen:
                seen.add(key)
                categories.append(category)
            if len(categories) >= limit:
                break
        return categories

    async def _category_keyboard(user_id):
        categories = await _category_options(user_id)
        rows = [
            [InlineKeyboardButton(f"📂 {category}", callback_data=f"category_pick_{index}")]
            for index, category in enumerate(categories)
        ]
        rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="category_skip")])
        return InlineKeyboardMarkup(rows)

    # Preserve the real optional-field callback (including tags/description).
    # Only category_pick_* is intercepted here.
    original_optional = task_handler.optional_field_callback

    async def _safe_optional_field_callback(update, context):
        query = update.callback_query
        data = query.data or ""
        if not data.startswith("category_pick_"):
            return await original_optional(update, context)

        task = context.user_data.get("new_task")
        if not isinstance(task, dict):
            await query.answer("فرایند ایجاد تسک فعال نیست.", show_alert=True)
            return
        try:
            index = int(data[len("category_pick_"):])
        except (TypeError, ValueError):
            await query.answer("دسته‌بندی انتخاب‌شده معتبر نیست.", show_alert=True)
            return

        categories = await _category_options(update.effective_user.id)
        if index < 0 or index >= len(categories):
            await query.answer("این دسته‌بندی دیگر در دسترس نیست.", show_alert=True)
            return

        await query.answer()
        task["category"] = categories[index]
        # _ask_tags is intentionally resolved at click time. By this point
        # handlers.tag_suggestions.install_tag_flow has already installed the
        # DB-backed tag suggestion keyboard.
        await task_handler._ask_tags(query.message, context)

    task_handler._category_keyboard = _category_keyboard
    task_handler._safe_category_optional_callback = _safe_optional_field_callback
    task_handler._safe_category_flow_installed = True


def _wrap_tag_flow_installer(tag_module):
    """Ensure the normal tag flow installs before category interception."""
    original = getattr(tag_module, "install_tag_flow", None)
    if original is None or getattr(original, "_taskmg_wrapped", False):
        return

    @wraps(original)
    def _wrapped_install_tag_flow(task_module):
        result = original(task_module)
        _install_safe_category_flow(task_module)
        return result

    _wrapped_install_tag_flow._taskmg_wrapped = True
    tag_module.install_tag_flow = _wrapped_install_tag_flow


# Import hook: after the real modules finish importing, install the adapters.
try:
    _original_import = builtins.__import__
    if not getattr(_original_import, "_taskmg_import_hook", False):
        @wraps(_original_import)
        def _taskmg_import(name, globals=None, locals=None, fromlist=(), level=0):
            module = _original_import(name, globals, locals, fromlist, level)
            try:
                task_module = sys.modules.get("handlers.task")
                if task_module is not None and (name == "handlers.task" or (name == "handlers" and "task" in (fromlist or ()) )):
                    _install_safe_category_flow(task_module)
                tag_module = sys.modules.get("handlers.tag_suggestions")
                if tag_module is not None and (name == "handlers.tag_suggestions" or (name == "handlers" and "tag_suggestions" in (fromlist or ()) )):
                    _wrap_tag_flow_installer(tag_module)
            except Exception:
                # Never prevent the bot from starting because of a compatibility hook.
                pass
            return module

        _taskmg_import._taskmg_import_hook = True
        builtins.__import__ = _taskmg_import
except Exception:
    pass

# main.py imports optional_field_callback directly. Replace the callback only
# when Telegram constructs the category/optional handler, so tags_skip and
# description_skip continue using the original tag-flow implementation.
try:
    from telegram.ext import CallbackQueryHandler
    _original_callback_handler_init = CallbackQueryHandler.__init__
    if not getattr(_original_callback_handler_init, "_taskmg_category_handler", False):
        @wraps(_original_callback_handler_init)
        def _category_safe_callback_handler_init(self, callback, pattern=None, *args, **kwargs):
            if getattr(callback, "__name__", "") == "optional_field_callback" and pattern and "category_pick_" in str(pattern):
                task_module = sys.modules.get("handlers.task")
                safe_callback = getattr(task_module, "_safe_category_optional_callback", None) if task_module else None
                if safe_callback is not None:
                    callback = safe_callback
            return _original_callback_handler_init(self, callback, pattern, *args, **kwargs)

        _category_safe_callback_handler_init._taskmg_category_handler = True
        CallbackQueryHandler.__init__ = _category_safe_callback_handler_init
except Exception:
    pass
