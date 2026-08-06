from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.templates import list_templates, get_template, expand_template
from services.task_service import create_task


def templates_menu_keyboard():
    buttons = []
    for t in list_templates():
        buttons.append([
            InlineKeyboardButton(
                t["title"],
                callback_data=f"tpl_view_{t['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="tpl_back")
    ])
    return InlineKeyboardMarkup(buttons)


async def show_templates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "# 🧩 تمپلیت‌ها\n\n"
        "یک برنامه از پیش‌آماده انتخاب کنید تا به‌صورت خودکار "
        "به لیست تسک‌های شما اضافه شود (از امروز به بعد).\n"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            text,
            reply_markup=templates_menu_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=templates_menu_keyboard(),
            parse_mode="Markdown"
        )


async def templates_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "tpl_back":
        from handlers.menu import main_menu
        await query.message.reply_text(
            "منوی اصلی:",
            reply_markup=main_menu()
        )
        return

    if data.startswith("tpl_view_"):
        tpl_id = data.replace("tpl_view_", "", 1)
        tpl = get_template(tpl_id)
        if not tpl:
            await query.message.reply_text("تمپلیت پیدا نشد.")
            return

        steps = tpl["steps"]
        preview = (
            f"# {tpl['title']}\n\n"
            f"{tpl['description']}\n\n"
            f"📂 دسته: {tpl.get('category', '—')}\n"
            f"🏷 تگ: {tpl.get('tags', '—')}\n"
            f"📌 تعداد مراحل: **{len(steps)}**\n\n"
            f"چند مرحله اول:\n"
        )

        for i, step in enumerate(steps[:5], start=1):
            preview += f"{i}. {step['title']} (روز {step['day_offset']})\n"

        if len(steps) > 5:
            preview += f"... و {len(steps) - 5} مرحله دیگر\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ اعمال این تمپلیت",
                    callback_data=f"tpl_apply_{tpl_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به لیست",
                    callback_data="tpl_menu"
                )
            ],
        ])

        await query.message.reply_text(
            preview,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    if data == "tpl_menu":
        await show_templates_menu(update, context)
        return

    if data.startswith("tpl_apply_"):
        tpl_id = data.replace("tpl_apply_", "", 1)
        tpl = get_template(tpl_id)
        if not tpl:
            await query.message.reply_text("تمپلیت پیدا نشد.")
            return

        tasks_data = expand_template(tpl)
        user_id = update.effective_user.id
        created_ids = []

        for item in tasks_data:
            task_id = create_task(
                user_id=user_id,
                title=item["title"],
                priority=item["priority"],
                deadline=item["deadline"],
                category=item["category"],
                tags=item["tags"],
            )
            created_ids.append(task_id)

        await query.message.reply_text(
            f"✅ تمپلیت «{tpl['title']}» اعمال شد.\n"
            f"📌 {len(created_ids)} تسک از امروز به برنامه‌تان اضافه شد.\n\n"
            f"با /tasks می‌توانید لیست را ببینید."
        )
