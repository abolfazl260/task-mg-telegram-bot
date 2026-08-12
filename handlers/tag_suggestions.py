from .tag_suggestions_legacy import *
from .tag_suggestions_legacy import install_tag_flow as _legacy_install_tag_flow


def install_tag_flow(task_module):
    """Install the legacy tag flow plus the three-mode /add entry flow."""
    _legacy_install_tag_flow(task_module)

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from services.groq_service import parse_task_request, GroqConfigurationError, GroqRequestError
    from handlers import ai as ai_module
    import asyncio
    import types

    async def _add_mode_entry(update, context):
        context.user_data["new_task"] = {}
        context.user_data["step"] = "add_mode"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 ثبت تکی", callback_data="add_task_single")],
            [InlineKeyboardButton("📥 ثبت گروهی", callback_data="import_bulk")],
            [InlineKeyboardButton("🤖 ثبت با هوش مصنوعی", callback_data="ai_task_create")],
        ])
        await update.message.reply_text(
            "📝 روش ثبت تسک را انتخاب کنید:",
            reply_markup=keyboard,
        )

    # main.py imports add_task by object reference before install_tag_flow runs.
    # Replace the function code in-place so that the already-imported handler uses the new flow.
    task_module._add_mode_entry = _add_mode_entry
    def _patched_add_task(update, context):
        return _add_mode_entry(update, context)
    task_module.add_task.__code__ = _patched_add_task.__code__

    # Preserve the original save_task as a separate function object, then intercept only the AI mode.
    original_save = types.FunctionType(
        task_module.save_task.__code__,
        task_module.save_task.__globals__,
        name="_original_save_task",
        argdefs=task_module.save_task.__defaults__,
        closure=task_module.save_task.__closure__,
    )
    task_module._original_save_task = original_save

    async def _ai_save_interceptor(update, context):
        if context.user_data.get("step") != "ai_add":
            return await task_module._original_save_task(update, context)

        text = (update.effective_message.text or "").strip()
        if not text:
            await update.effective_message.reply_text("⚠️ لطفاً توضیح تسک را ارسال کنید.")
            return

        try:
            draft = await asyncio.to_thread(
                parse_task_request,
                update.effective_user.id,
                text,
            )
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
            await update.effective_message.reply_text(
                "🌱 این درخواست به‌عنوان عادت تشخیص داده شد.\n\n"
                "برای ثبت عادت، از /ai استفاده کنید."
            )
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
        if draft.get("category"):
            lines.append(f"📂 دسته‌بندی: {draft['category']}")
        if draft.get("tags"):
            lines.append(f"🏷 تگ: {draft['tags']}")
        if draft.get("description"):
            lines.append(f"📝 توضیحات: {draft['description']}")
        lines.extend(["", "آیا این تسک ایجاد شود?"])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ایجاد تسک", callback_data="ai_task_create")],
            [InlineKeyboardButton("❌ لغو", callback_data="ai_task_cancel")],
        ])
        await update.effective_message.reply_text("\n".join(lines), reply_markup=keyboard)

    task_module.save_task.__code__ = _ai_save_interceptor.__code__

    # Reuse the existing AI callback/service. The first click enters AI-input mode;
    # a later click with a populated draft is delegated to the existing callback.
    original_ai_callback = types.FunctionType(
        ai_module.ai_task_callback.__code__,
        ai_module.ai_task_callback.__globals__,
        name="_original_ai_task_callback",
        argdefs=ai_module.ai_task_callback.__defaults__,
        closure=ai_module.ai_task_callback.__closure__,
    )
    ai_module._original_ai_task_callback = original_ai_callback

    async def _ai_add_callback(update, context):
        query = update.callback_query
        if (query.data or "") == "ai_task_create" and not context.user_data.get("ai_request_draft"):
            await query.answer()
            context.user_data["step"] = "ai_add"
            context.user_data["new_task"] = {}
            await query.message.reply_text(
                "🤖 ثبت تسک با هوش مصنوعی\n\n"
                "در پیام بعدی، تسک را به زبان طبیعی توضیح دهید.\n\n"
                "💡 هرچه اطلاعات کامل‌تر باشد، پیشنهاد دقیق‌تری دریافت می‌کنید. "
                "می‌توانید عنوان یا موضوع، دسته‌بندی، تگ‌ها، اولویت، زمان یا مهلت و توضیحات را بنویسید.\n\n"
                "مثال:\n"
                "«فردا ساعت ۱۰ گزارش فروش را برای مدیر ارسال کنم؛ مالی، اولویت بالا، تگ گزارش و توضیح: نسخه نهایی باشد»"
            )
            return
        return await ai_module._original_ai_task_callback(update, context)

    ai_module._add_ai_callback = _ai_add_callback
    ai_module.ai_task_callback.__code__ = _ai_add_callback.__code__
