from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.task_service import get_all_user_tasks


def _split_tags(raw):
    if not raw:
        return []
    return [item.strip().lstrip("#") for item in str(raw).replace("\n", ",").replace("،", ",").split(",") if item.strip()]


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


def _tag_keyboard(user_id):
    rows = []
    for tag in get_suggested_tags(user_id):
        safe = tag[:50]
        rows.append([InlineKeyboardButton(f"🏷 {tag}", callback_data=f"tags_pick_{safe}")])
    rows.append([InlineKeyboardButton("➕ تگ جدید", callback_data="tags_new")])
    rows.append([InlineKeyboardButton("⏭ بدون تگ", callback_data="tags_skip")])
    return InlineKeyboardMarkup(rows)


async def ask_tags(message, context):
    context.user_data["step"] = "tags"
    await message.reply_text(
        "🏷 تگ را انتخاب کنید، یک تگ جدید وارد کنید یا بدون تگ ادامه دهید:",
        reply_markup=_tag_keyboard(message.chat.id if False else context._user_id if hasattr(context, "_user_id") else 0),
    )


def install_tag_flow(task_module):
    """Patch the existing task creation tag prompt without changing its flow."""
    async def _ask_tags(message, context):
        context.user_data["step"] = "tags"
        user_id = getattr(context, "_user_id", None)
        # PTB context does not expose user_id directly; use the message sender.
        if not user_id:
            user = getattr(message, "from_user", None)
            user_id = getattr(user, "id", None)
        if not user_id:
            user_id = getattr(getattr(message, "chat", None), "id", 0)
        await message.reply_text(
            "🏷 تگ را انتخاب کنید، یک تگ جدید وارد کنید یا بدون تگ ادامه دهید:",
            reply_markup=_tag_keyboard(user_id),
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
        from handlers.task import _ask_description
        await _ask_description(query.message, context)
        return

    if data == "tags_new":
        context.user_data["step"] = "tags"
        await query.message.reply_text("🏷 تگ جدید را وارد کنید؛ اگر نمی‌خواهید تگی اضافه شود، «بدون تگ» را بزنید.")
        return

    if data.startswith("tags_pick_"):
        selected = data.replace("tags_pick_", "", 1).strip()
        if not selected:
            await query.message.reply_text("⚠️ تگ انتخاب‌شده معتبر نیست.")
            return
        task["tags"] = selected
        from handlers.task import _ask_description
        await _ask_description(query.message, context)
        return


async def handle_tag_text(update, context):
    if context.user_data.get("step") != "tags":
        return False
    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        return False
    text = (update.effective_message.text or "").strip()
    if not text:
        return False
    if text in ("بدون تگ", "بدون", "ندارم", "هیچ"):
        task["tags"] = ""
    else:
        task["tags"] = text[:120]
    from handlers.task import _ask_description
    await _ask_description(update.effective_message, context)
    return True


async def safe_assignment_confirm(update, context):
    """Guard stale assignment confirmation callbacks before task.py indexes required fields."""
    if (update.callback_query.data or "") != "assign_confirm_create":
        return

    task = context.user_data.get("new_task")
    if not isinstance(task, dict):
        await update.callback_query.answer("فرایند ایجاد تسک منقضی شده است.", show_alert=True)
        await update.callback_query.message.reply_text("⚠️ اطلاعات تسک ناقص است. لطفاً تسک را دوباره از ابتدا ایجاد کنید.")
        context.user_data.clear()
        return

    missing = []
    if not (task.get("title") or "").strip():
        missing.append("عنوان")
    if task.get("priority") not in ("high", "medium", "low"):
        missing.append("اولویت")

    if missing:
        await update.callback_query.answer("اطلاعات تسک ناقص است.", show_alert=True)
        await update.callback_query.message.reply_text(
            "⚠️ امکان ثبت این تسک وجود ندارد چون اطلاعات زیر ناقص است:\n"
            + "، ".join(missing)
            + "\n\nلطفاً تسک را دوباره از ابتدا ایجاد کنید."
        )
        context.user_data.clear()
        return

    # Valid state: let the original assignment handler finish the normal flow.
    from handlers.task import assignment_callback
    await assignment_callback(update, context)
