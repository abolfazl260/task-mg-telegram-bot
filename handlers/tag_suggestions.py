from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import get_all_user_tasks


def _split_tags(raw):
    if not raw:
        return []
    return [
        item.strip().lstrip("#")
        for item in str(raw).replace("\n", ",").replace("،", ",").split(",")
        if item.strip()
    ]


def get_suggested_tags(user_id, limit=12):
    """Return tags previously used by the user or in teams visible to them."""
    seen = set()
    result = []
    for task in get_all_user_tasks(user_id):
        for tag in _split_tags(task.get("tags")):
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                result.append(tag)
            if len(result) >= limit:
                return result
    return result


def _tag_keyboard(tags, context):
    context.user_data["tag_suggestions"] = list(tags)
    rows = []
    for index, tag in enumerate(tags):
        rows.append([InlineKeyboardButton(f"🏷 {tag}", callback_data=f"tags_pick_{index}")])
    rows.append([InlineKeyboardButton("➕ تگ جدید", callback_data="tags_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ", callback_data="tags_skip")])
    return InlineKeyboardMarkup(rows)


def install_tag_flow(task_module):
    """Patch the existing task creation tag prompt with reusable tag suggestions."""
    async def _ask_tags(message, context):
        context.user_data["step"] = "tags"
        user = getattr(message, "from_user", None)
        user_id = getattr(user, "id", None) or getattr(getattr(message, "chat", None), "id", 0)
        tags = get_suggested_tags(user_id)
        await message.reply_text(
            "🏷 تگ را انتخاب کنید، یک تگ جدید وارد کنید یا بدون تگ ادامه دهید:",
            reply_markup=_tag_keyboard(tags, context),
        )

    task_module._ask_tags = _ask_tags


async def handle_tag_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("tags_"):
        return

    await query.answer()
    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        await query.message.reply_text("فرایند ایجاد تسک پیدا نشد. لطفاً دوباره از ابتدا شروع کنید.")
        context.user_data.pop("step", None)
        return

    if data == "tags_skip":
        task["tags"] = ""
        context.user_data.pop("tag_suggestions", None)
        from handlers.task import _ask_description
        await _ask_description(query.message, context)
        return

    if data == "tags_new":
        context.user_data["step"] = "tags"
        await query.message.reply_text("🏷 تگ جدید را وارد کنید؛ اگر نمی‌خواهید تگی اضافه شود، «بدون تگ» را بزنید.")
        return

    if data.startswith("tags_pick_"):
        try:
            index = int(data.replace("tags_pick_", "", 1))
        except ValueError:
            await query.message.reply_text("⚠️ تگ انتخاب‌شده معتبر نیست.")
            return

        suggestions = context.user_data.get("tag_suggestions") or []
        if index < 0 or index >= len(suggestions):
            await query.message.reply_text("⚠️ این پیشنهاد تگ دیگر معتبر نیست. لطفاً دوباره تگ‌ها را انتخاب کنید.")
            return

        task["tags"] = suggestions[index]
        context.user_data.pop("tag_suggestions", None)
        from handlers.task import _ask_description
        await _ask_description(query.message, context)
        return


async def handle_tag_text(update, context):
    """Handle tag text while allowing every other task-creation step through.

    This handler is registered before save_task in main.py. Telegram's
    MessageHandler stops dispatching within the same group after a match,
    regardless of the callback's return value. Therefore non-tag steps must
    explicitly delegate to save_task instead of simply returning False.
    """
    if context.user_data.get("step") != "tags":
        from handlers.task import save_task
        await save_task(update, context)
        return True

    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        return False
    message = update.effective_message
    text = (message.text or "").strip()
    if not text:
        return False

    if text in ("بدون تگ", "بدون", "ندارم", "هیچ"):
        task["tags"] = ""
    else:
        task["tags"] = text[:120]

    context.user_data.pop("tag_suggestions", None)
    from handlers.task import _ask_description
    await _ask_description(message, context)
    return True


async def safe_assignment_confirm(update, context):
    """Guard stale confirmation callbacks before task.py indexes required fields."""
    query = update.callback_query
    if (query.data or "") != "assign_confirm_create":
        return

    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        await query.answer("فرایند ایجاد تسک منقضی شده است.", show_alert=True)
        await query.message.reply_text("⚠️ اطلاعات تسک ناقص است. لطفاً تسک را دوباره از ابتدا ایجاد کنید.")
        context.user_data.clear()
        return

    missing = []
    if not (task.get("title") or "").strip():
        missing.append("عنوان")
    if task.get("priority") not in ("high", "medium", "low"):
        missing.append("اولویت")

    if missing:
        await query.answer("اطلاعات تسک ناقص است.", show_alert=True)
        await query.message.reply_text(
            "⚠️ امکان ثبت این تسک وجود ندارد چون اطلاعات زیر ناقص است:\n"
            + "، ".join(missing)
            + "\n\nلطفاً تسک را دوباره از ابتدا ایجاد کنید."
        )
        context.user_data.clear()
        return

    from handlers.task import assignment_callback
    await assignment_callback(update, context)
