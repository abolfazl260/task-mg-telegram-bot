import asyncio
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes

from handlers.menu import main_menu
from services.team_service import join_team_by_code, find_team_by_code


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
        bot_description = f"\n{profile.description}\n" if profile and profile.description else ""
        text = f"""
# 👋 سلام {user.first_name}

## 📋 {bot_name}
{bot_description}

دستیار هوشمند مدیریت کارها، جلسات و اقدامات شما آماده است.

🚀 امکانات فعلی:

✅ ایجاد و مدیریت تسک
📅 تعیین زمان انجام
🎯 اولویت‌بندی کارها
👥 تیم و فضای مشترک
📋 مشاهده لیست تسک‌های فعال
⏳ محاسبه زمان باقی‌مانده
📊 داشبورد وضعیت کارها

---

## 🎯 اولویت‌ها
a
🔴 بالا
کارهای مهم و فوری

🟠 متوسط
کارهای روزمره

🟢 پایین
کارهای قابل برنامه‌ریزی

---

## 📌 وضعیت‌ها

⏳ در انتظار
🚀 در حال انجام
✅ انجام شده

برای شروع یکی از گزینه‌های زیر را انتخاب کنید 👇
"""

    await context.bot._post(
        "sendRichMessage",
        data={"chat_id": update.effective_chat.id, "rich_message": {"markdown": text}},
    )

    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu(context))
