import asyncio
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes

from handlers.menu import main_menu, main_menu_summary
from services.team_service import join_team_by_code, find_team_by_code

# main.py imports `start` before it imports the legacy `add_task` symbol.
# Install the canonical task-creation flow at this point so that the later
# `from handlers.task import add_task` resolves to the Rich implementation.
from handlers import task as task_handler
from handlers.tag_suggestions import install_tag_flow

if not getattr(task_handler, "_tag_flow_installed", False):
    install_tag_flow(task_handler)


async def _team_call(fn, *args, **kwargs):
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    payload = (context.args[0] or "").strip() if context.args else ""
    if payload:
        code = payload
        for prefix in ("join_", "team_", "JOIN_", "TEAM_"):
            if code.startswith(prefix):
                code = code[len(prefix):]
                break
        code = code.strip()

        if code:
            team_preview, role_preview = await _team_call(find_team_by_code, code)
            if team_preview:
                role_fa = (
                    "ویرایشگر (می‌تواند تسک بسازد و تغییر دهد)"
                    if role_preview == "editor"
                    else "مشاهده‌کننده (فقط مشاهده)"
                )
                ok, msg, team = await _team_call(join_team_by_code, user.id, code, user=user)
                if ok and team:
                    await update.message.reply_text(
                        f"✅ عضویت موفق\n\n"
                        f"📂 تیم: **{team['name']}**\n"
                        f"🆔 `{team['team_id']}`\n"
                        f"نقش شما: {role_fa}\n\n"
                        f"{msg}",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ {msg}\n\n📂 تیم: **{team_preview['name']}**"
                        if team_preview else f"⚠️ {msg}",
                        parse_mode="Markdown",
                    )
            else:
                await update.message.reply_text("⚠️ کد دعوت نامعتبر است یا تیم پیدا نشد.")

    profile = context.bot_data.get("bot_config")
    bot_name = profile.name if profile else "Task Manager Bot"
    ui = (profile.settings or {}).get("ui", {}) if profile else {}
    custom_start = ui.get("start_text") if isinstance(ui, dict) else None

    if custom_start:
        text = custom_start.replace("{first_name}", user.first_name or "")
    else:
        text = f"""
👋 سلام {user.first_name}

به دستیار مدیریت کارها خوش آمدی 🤖

با من می‌تونی:
✅ تسک بسازی و مدیریت کنی
🎙️ با صدای فارسی تسک ایجاد کنی
📅 برای کارهات زمان تعیین کنی
🎯 اولویت مشخص کنی
👥 تسک‌ها رو با هم‌تیمی‌هات به اشتراک بذاری
📊 گزارش‌های مختلف بگیری
"""

    await context.bot._post(
        "sendRichMessage",
        data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}},
    )

    await update.message.reply_text(
        main_menu_summary(user.id) + "\n\nمنوی اصلی:",
        reply_markup=main_menu(context),
        parse_mode="Markdown",
    )
