from .tag_suggestions_legacy import *
from .tag_suggestions_legacy import install_tag_flow as _legacy_install_tag_flow

MAX_TASK_FIELD_LENGTH = 30


async def handle_tag_text(update, context):
    """Handle a typed tag before delegating to the normal task text flow."""
    from handlers import task as task_module

    if context.user_data.get("step") != "tags":
        return await task_module.save_task(update, context)

    task = context.user_data.get("new_task")
    text = (update.effective_message.text or "").strip()
    if not isinstance(task, dict) or not text:
        return await task_module.save_task(update, context)

    if len(text) > MAX_TASK_FIELD_LENGTH:
        await update.effective_message.reply_text(
            f"⚠️ تگ نمی‌تواند بیشتر از {MAX_TASK_FIELD_LENGTH} کاراکتر باشد.\n"
            "لطفاً تگ کوتاه‌تری وارد کنید."
        )
        return True

    task["tags"] = text
    context.user_data.pop("tag_suggestions", None)
    context.user_data.pop("awaiting_tag_input", None)
    await task_module._ask_description(update.effective_message, context)
    return True


def _patched_add_task(update, context):
    return _ADD_MODE_ENTRY(update, context)


def _patched_save_task(update, context):
    return _AI_SAVE_INTERCEPTOR(update, context)


def _patched_ai_task_callback(update, context):
    return _AI_ADD_CALLBACK(update, context)


def _truncate_field(value):
    return str(value or "").strip()[:MAX_TASK_FIELD_LENGTH]


def _patched_category_keyboard_factory(task_module):
    async def category_keyboard(user_id):
        categories = []
        seen = set()
        for task in await task_module.get_active_tasks_async(user_id):
            category = (task.get("category") or "").strip()
            key = category.casefold()
            if category and key not in seen:
                seen.add(key)
                categories.append(_truncate_field(category))
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [
            [InlineKeyboardButton(f"📂 {category}", callback_data=f"category_pick_{category}")]
            for category in categories[:10]
        ]
        rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="category_skip")])
        return InlineKeyboardMarkup(rows)
    return category_keyboard


async def _patched_handle_tag_text(update, context):
    return await handle_tag_text(update, context)


def install_tag_flow(task_module):
    """Install the shared /add and AI flow exactly once per process."""
    if getattr(task_module, "_tag_flow_installed", False):
        return

    _legacy_install_tag_flow(task_module)

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from services.groq_service import parse_task_request, GroqConfigurationError, GroqRequestError
    from services.task_capabilities import task_option_enabled, wrap_save_task
    from handlers import ai as ai_module
    import asyncio
    import types

    async def add_mode_entry(update, context):
        query = update.callback_query
        message = update.effective_message
        if message is None and query is not None:
            message = query.message
        if message is None:
            return

        # The single-task button enters the same flow used by /add.
        if query is not None and query.data == "add_task_manual":
            context.user_data["new_task"] = {}
            context.user_data["step"] = "title"
            await message.reply_text("📝 عنوان تسک را وارد کنید:")
            return

        context.user_data["new_task"] = {}
        context.user_data["step"] = "add_mode"
        rows = [[InlineKeyboardButton("📝 ثبت تکی", callback_data="add_task_manual")]]
        if task_option_enabled(context, "allow_bulk_import"):
            rows.append([InlineKeyboardButton("📥 ثبت گروهی", callback_data="import_bulk")])
        if task_option_enabled(context, "allow_ai_task_creation"):
            rows.append([InlineKeyboardButton("🤖 ثبت با هوش مصنوعی", callback_data="ai_task_create")])
        await message.reply_text("📝 روش ثبت تسک را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))

    task_module._ADD_MODE_ENTRY = add_mode_entry
    task_module.add_task.__code__ = _patched_add_task.__code__

    original_save = types.FunctionType(
        task_module.save_task.__code__, task_module.save_task.__globals__,
        name="_original_save_task", argdefs=task_module.save_task.__defaults__, closure=task_module.save_task.__closure__
    )
    task_module._original_save_task = original_save
    task_module._capability_save_task = wrap_save_task(original_save)

    async def ai_save_interceptor(update, context):
        step = context.user_data.get("step")
        text = (update.effective_message.text or "").strip()

        # Enforce the same limit for manual category/tag input and do not
        # silently truncate user input.
        if step in ("category", "tags") and len(text) > MAX_TASK_FIELD_LENGTH:
            field_name = "دسته‌بندی" if step == "category" else "تگ"
            await update.effective_message.reply_text(
                f"⚠️ {field_name} نمی‌تواند بیشتر از {MAX_TASK_FIELD_LENGTH} کاراکتر باشد.\n"
                f"لطفاً {field_name} کوتاه‌تری وارد کنید."
            )
            return

        if step != "ai_add":
            return await task_module._capability_save_task(update, context)
        if not text:
            await update.effective_message.reply_text("⚠️ لطفاً توضیح تسک را ارسال کنید.")
            return
        try:
            draft = await asyncio.to_thread(parse_task_request, update.effective_user.id, text)
        except GroqConfigurationError:
            await update.effective_message.reply_text("⚠️ دستیار هوشمند در حال حاضر فعال نیست.")
            context.user_data.pop("step", None)
            return
        except GroqRequestError as exc:
            await update.effective_message.reply_text(f"⚠️ {exc}")
            return
        except Exception:
            await update.effective_message.reply_text("⚠️ پردازش درخواست انجام نشد. لطفاً متن را دوباره ارسال کنید.")
            return
        if draft.get("action") == "CREATE_HABIT":
            await update.effective_message.reply_text("🌱 این درخواست به‌عنوان عادت تشخیص داده شد.\n\nبرای ثبت عادت، از /ai استفاده کنید.")
            return
        if draft.get("action") != "CREATE_TASK":
            await update.effective_message.reply_text("⚠️ درخواست قابل تبدیل به تسک نیست.")
            return
        context.user_data["ai_request_draft"] = draft
        context.user_data["step"] = "ai_add_confirm"
        priority_labels = {"high": "🔴 بالا", "medium": "🟠 متوسط", "low": "🟢 پایین"}
        lines = ["🤖 تسک پیشنهادی هوش مصنوعی", "", f"📌 عنوان: {draft['title']}"]
        if draft.get("deadline"):
            lines.append(f"🗓 زمان: {draft['deadline']}")
        lines.append(f"🎯 اولویت: {priority_labels.get(draft.get('priority'), '🟢 پایین')}")
        if draft.get("category") and task_option_enabled(context, "allow_categories"):
            lines.append(f"📂 دسته‌بندی: {_truncate_field(draft['category'])}")
        if draft.get("tags") and task_option_enabled(context, "allow_tags"):
            lines.append(f"🏷 تگ: {_truncate_field(draft['tags'])}")
        if draft.get("description"):
            lines.append(f"📝 توضیحات: {draft['description']}")
        lines.extend(["", "آیا این تسک ایجاد شود?"])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ایجاد تسک", callback_data="ai_task_create")],
            [InlineKeyboardButton("❌ لغو", callback_data="ai_task_cancel")],
        ])
        await update.effective_message.reply_text("\n".join(lines), reply_markup=keyboard)

    task_module._AI_SAVE_INTERCEPTOR = ai_save_interceptor
    task_module.save_task.__code__ = _patched_save_task.__code__

    # Always render previously-used tags when entering the tag step.
    async def ask_tags_with_suggestions(message, context):
        context.user_data["step"] = "tags"
        user = getattr(message, "from_user", None)
        user_id = getattr(user, "id", 0)
        keyboard, tags = await recent_tag_keyboard(user_id, limit=3)
        context.user_data["tag_suggestions"] = tags
        await message.reply_text(
            "🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:",
            reply_markup=keyboard,
        )

    task_module._ask_tags = ask_tags_with_suggestions
    task_module._category_keyboard = _patched_category_keyboard_factory(task_module)
    task_module._handle_tag_text = _patched_handle_tag_text

    original_ai_callback = types.FunctionType(
        ai_module.ai_task_callback.__code__, ai_module.ai_task_callback.__globals__,
        name="_original_ai_task_callback", argdefs=ai_module.ai_task_callback.__defaults__, closure=ai_module.ai_task_callback.__closure__
    )
    ai_module._original_ai_task_callback = original_ai_callback

    async def ai_add_callback(update, context):
        query = update.callback_query
        if (query.data or "") == "ai_task_create" and not context.user_data.get("ai_request_draft"):
            if not task_option_enabled(context, "allow_ai_task_creation"):
                await query.answer("ایجاد تسک با هوش مصنوعی برای این ربات فعال نیست.", show_alert=True)
                return
            await query.answer()
            context.user_data["step"] = "ai_add"
            context.user_data["new_task"] = {}
            await query.message.reply_text(
                "🤖 ثبت تسک با هوش مصنوعی\n\nدر پیام بعدی، تسک را به زبان طبیعی توضیح دهید.\n\n💡 برای پیشنهاد دقیق‌تر، موضوع یا عنوان، دسته‌بندی، تگ‌ها، اولویت، زمان یا مهلت و توضیحات را بنویسید.\n\nمثال:\n«فردا ساعت ۱۰ گزارش فروش را برای مدیر ارسال کنم؛ دسته مالی، اولویت بالا، تگ گزارش و توضیح: نسخه نهایی باشد»"
            )
            return
        return await ai_module._original_ai_task_callback(update, context)

    ai_module._AI_ADD_CALLBACK = ai_add_callback
    ai_module.ai_task_callback.__code__ = _patched_ai_task_callback.__code__
    task_module._tag_flow_installed = True
