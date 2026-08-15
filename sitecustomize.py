"""Python compatibility, Telegram command-menu ordering, and safe task-category callbacks."""
import asyncio
from functools import wraps

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


# Telegram exposes commands in the order supplied to set_my_commands().
# Keep the requested primary commands at the top, always keep /start visible,
# remove /templates from the menu, and preserve the legacy order of everything
# else.
try:
    from telegram import Bot, BotCommand

    _original_set_my_commands = Bot.set_my_commands

    if not getattr(_original_set_my_commands, "_taskmg_ordered", False):
        _command_priority = {"ai": 0, "start": 1, "add": 2, "reports": 3}

        @wraps(_original_set_my_commands)
        async def _ordered_set_my_commands(self, commands, *args, **kwargs):
            commands = [command for command in list(commands) if command.command != "templates"]
            if not any(command.command == "start" for command in commands):
                commands.append(BotCommand("start", "شروع ربات و منوی اصلی"))
            indexed = list(enumerate(commands))
            indexed.sort(key=lambda item: (_command_priority.get(item[1].command, 1000), item[0]))
            return await _original_set_my_commands(self, [command for _, command in indexed], *args, **kwargs)

        _ordered_set_my_commands._taskmg_ordered = True
        Bot.set_my_commands = _ordered_set_my_commands
except Exception:
    pass


# Telegram callback_data is limited to 64 UTF-8 bytes, not 64 Python
# characters. The previous category buttons embedded the category text in
# callback_data, which breaks for Persian/other multi-byte category names.
# Keep the visible category text, but use a short numeric identifier instead.
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import handlers.task as _task_handler

    if not getattr(_task_handler, "_safe_category_flow_installed", False):
        async def _safe_category_keyboard(user_id):
            categories = []
            seen = set()
            for task in await _task_handler.get_active_tasks_async(user_id):
                category = (task.get("category") or "").strip()
                key = category.lower()
                if category and key not in seen:
                    seen.add(key)
                    categories.append(category)
            rows = [
                [InlineKeyboardButton(f"📂 {category}", callback_data=f"category_pick_{index}")]
                for index, category in enumerate(categories[:10])
            ]
            rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="category_skip")])
            return InlineKeyboardMarkup(rows)

        _original_category_callback = _task_handler.optional_field_callback

        async def _safe_optional_field_callback(update, context):
            query = update.callback_query
            data = query.data or ""
            if not data.startswith("category_pick_"):
                return await _original_category_callback(update, context)

            await query.answer()
            task = context.user_data.get("new_task")
            if not task:
                await query.message.reply_text("فرایند ایجاد تسک فعالی پیدا نشد.")
                return

            try:
                index = int(data.removeprefix("category_pick_"))
            except ValueError:
                await query.message.reply_text("⚠️ دسته‌بندی انتخاب‌شده معتبر نیست.")
                return

            categories = []
            seen = set()
            for item in await _task_handler.get_active_tasks_async(update.effective_user.id):
                category = (item.get("category") or "").strip()
                key = category.lower()
                if category and key not in seen:
                    seen.add(key)
                    categories.append(category)

            if index < 0 or index >= min(len(categories), 10):
                await query.message.reply_text("⚠️ دسته‌بندی انتخاب‌شده دیگر در دسترس نیست.")
                return

            task["category"] = categories[index]
            await _task_handler._ask_tags(query.message, context)

        _task_handler._category_keyboard = _safe_category_keyboard
        _task_handler.optional_field_callback = _safe_optional_field_callback
        _task_handler._safe_category_flow_installed = True
except Exception:
    # Never prevent the bot from starting if an optional Telegram/task import
    # is unavailable during interpreter initialization.
    pass
