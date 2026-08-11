from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import ContextTypes

import handlers.menu as menu_handler
import handlers.reports as reports_handler
from services.kanban_pdf_service import build_kanban_pdf
from services.permission_service import (
    PERMISSION_KANBAN_PDF,
    PERMISSION_KANBAN_PDF_LABEL,
    has_permission,
    is_admin,
    list_users_for_permission,
    set_permission,
)
from services.task_service import get_all_user_tasks_async


def _with_pdf_button(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    rows = [
        list(row)
        for row in markup.inline_keyboard
        if not any(button.callback_data == "report_kanban_pdf" for button in row)
    ]
    rows.append([InlineKeyboardButton("📄 ایجاد PDF کانبان برد", callback_data="report_kanban_pdf")])
    return InlineKeyboardMarkup(rows)


async def show_reports_menu_with_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        message = update.message

    markup = reports_handler.reports_menu_keyboard()
    if await has_permission(user_id, PERMISSION_KANBAN_PDF):
        markup = _with_pdf_button(markup)
    await message.reply_text(
        "# 📊 بخش گزارشات\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=markup,
        parse_mode="Markdown",
    )


_ORIGINAL_SETTINGS_KEYBOARD = menu_handler.settings_keyboard


def install_access_ui() -> None:
    """Expose access management in Settings only to configured admins."""
    from services.calendar_runtime_extensions import viewer_id

    def settings_keyboard_with_access(context=None):
        markup = _ORIGINAL_SETTINGS_KEYBOARD(context)
        if not is_admin(viewer_id()):
            return markup
        rows = [list(row) for row in markup.inline_keyboard]
        if not any(button.callback_data == "settings_permissions" for row in rows for button in row):
            rows.append([InlineKeyboardButton("🔐 مدیریت دسترسی‌ها", callback_data="settings_permissions")])
        return InlineKeyboardMarkup(rows)

    menu_handler.settings_keyboard = settings_keyboard_with_access


async def _permission_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("⛔ دسترسی مدیریت مجوزها را ندارید.")
        return

    users = await list_users_for_permission(PERMISSION_KANBAN_PDF)
    rows = []
    for user in users[:40]:
        uid = str(user.get("user_id") or "")
        name = (user.get("full_name") or "").strip() or uid
        state = "فعال" if user.get("has_permission") else "غیرفعال"
        rows.append([InlineKeyboardButton(f"{name[:28]} — {state}", callback_data=f"perm_toggle_{uid}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="settings")])
    text = (
        "🔐 **مدیریت دسترسی‌ها**\n\n"
        f"مجوز: **{PERMISSION_KANBAN_PDF_LABEL}**\n\n"
        "برای هر کاربر، وضعیت مجوز را انتخاب کنید."
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(rows))


async def _toggle_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("⛔ دسترسی مدیریت مجوزها را ندارید.")
        return
    target_id = query.data.removeprefix("perm_toggle_")
    users = await list_users_for_permission(PERMISSION_KANBAN_PDF)
    target = next((user for user in users if str(user.get("user_id")) == target_id), None)
    if not target:
        await query.message.reply_text("⚠️ کاربر پیدا نشد.")
        return
    if is_admin(target_id):
        await query.answer("مجوز مدیر اصلی قابل لغو نیست.", show_alert=True)
        return
    new_value = not bool(target.get("has_permission"))
    await set_permission(target_id, PERMISSION_KANBAN_PDF, new_value)
    await query.answer("مجوز فعال شد." if new_value else "مجوز غیرفعال شد.")
    await _permission_dashboard(update, context)


async def kanban_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not await has_permission(user_id, PERMISSION_KANBAN_PDF):
        await query.message.reply_text("⛔ شما دسترسی «ایجاد PDF کانبان برد» را ندارید.")
        return

    tasks = await get_all_user_tasks_async(user_id)
    if not tasks:
        await query.message.reply_text("هنوز هیچ تسکی برای ساخت کانبان برد وجود ندارد.")
        return

    try:
        pdf = build_kanban_pdf(tasks)
    except ValueError as exc:
        await query.message.reply_text(str(exc))
        return
    except Exception:
        await query.message.reply_text("⚠️ تولید PDF کانبان برد ناموفق بود. لطفاً دوباره تلاش کنید.")
        return

    await query.message.reply_document(
        document=InputFile(pdf, filename="kanban-board.pdf"),
        caption="📄 فایل PDF کانبان برد آماده است.",
    )


async def access_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "settings_permissions":
        await _permission_dashboard(update, context)
    else:
        await _toggle_permission(update, context)
