"""Python compatibility, Telegram command ordering, and safe task-category callbacks."""
import asyncio
import builtins
from functools import wraps

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Telegram exposes commands in the order supplied to set_my_commands().
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
    """Patch category callbacks after handlers.task has fully imported.

    Telegram callback_data is limited to 64 UTF-8 bytes. Category names can be
    long Persian strings, so the callback must contain a short ASCII index.
    """
    if getattr(task_handler, "_safe_category_flow_installed", False):
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    async def _safe_category_keyboard(user_id):
        categories = []
        seen = set()
        for task in await task_handler.get_active_tasks_async(user_id):
            category = (task.get("category") or "").strip()
            key = category.casefold()
            if category and key not in seen:
                seen.add(key)
                categories.append(category)
        rows = [
            [InlineKeyboardButton(f"📂 {category}", callback_data=f"category_pick_{index}")]
            for index, category in enumerate(categories[:10])
        ]
        rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="category_skip")])
        return InlineKeyboardMarkup(rows)

    original_optional = task_handler.optional_field_callback

    async def _safe_optional_field_callback(update, context):
        query = update.callback_query
        data = query.data or ""
        if not data.startswith("category_pick_"):
            return await original_optional(update, context)

        await query.answer()
        task = context.user_data.get("new_task")
        if not task:
            await query.message.reply_text("فرایند ایجاد تسک فعالی پیدا نشد.")
            return

        try:
            index = int(data[len("category_pick_"):])
        except (TypeError, ValueError):
            await query.message.reply_text("⚠️ دسته‌بندی انتخاب‌شده معتبر نیست.")
            return

        categories = []
        seen = set()
        for item in await task_handler.get_active_tasks_async(update.effective_user.id):
            category = (item.get("category") or "").strip()
            key = category.casefold()
            if category and key not in seen:
                seen.add(key)
                categories.append(category)

        if index < 0 or index >= min(len(categories), 10):
            await query.message.reply_text("⚠️ این دسته‌بندی دیگر در دسترس نیست. لطفاً دوباره انتخاب کنید.")
            return

        task["category"] = categories[index]
        await task_handler._ask_tags(query.message, context)

    task_handler._category_keyboard = _safe_category_keyboard
    task_handler.optional_field_callback = _safe_optional_field_callback
    task_handler._safe_category_flow_installed = True


# Do not import handlers.task directly here: doing so during interpreter
# startup can create a circular import. Instead, patch it immediately after
# Python imports the module (including when main.py imports its functions).
try:
    _original_import = builtins.__import__

    if not getattr(_original_import, "_taskmg_category_hook", False):
        @wraps(_original_import)
        def _taskmg_import(name, globals=None, locals=None, fromlist=(), level=0):
            module = _original_import(name, globals, locals, fromlist, level)
            if name == "handlers.task" or (name == "handlers" and "task" in (fromlist or ())):
                try:
                    import sys
                    task_module = sys.modules.get("handlers.task")
                    if task_module is not None:
                        _install_safe_category_flow(task_module)
                except Exception:
                    pass
            return module

        _taskmg_import._taskmg_category_hook = True
        builtins.__import__ = _taskmg_import
except Exception:
    pass

# main.py imports optional_field_callback directly with a `from ... import`.
# Replacing only task_handler.optional_field_callback therefore leaves main's
# local reference pointing to the old implementation. Intercept construction
# of the category CallbackQueryHandler so that the safe implementation is used
# for the actual runtime handler as well.
try:
    from telegram.ext import CallbackQueryHandler
    _original_callback_handler_init = CallbackQueryHandler.__init__
    if not getattr(_original_callback_handler_init, "_taskmg_category_handler", False):
        @wraps(_original_callback_handler_init)
        def _category_safe_callback_handler_init(self, callback, pattern=None, *args, **kwargs):
            if getattr(callback, "__name__", "") == "optional_field_callback" and pattern and "category_pick_" in str(pattern):
                try:
                    import sys
                    task_module = sys.modules.get("handlers.task")
                    safe_callback = getattr(task_module, "optional_field_callback", None) if task_module else None
                    if safe_callback is not None and safe_callback is not callback:
                        callback = safe_callback
                except Exception:
                    pass
            return _original_callback_handler_init(self, callback, pattern, *args, **kwargs)

        _category_safe_callback_handler_init._taskmg_category_handler = True
        CallbackQueryHandler.__init__ = _category_safe_callback_handler_init
except Exception:
    pass
