import asyncio
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from services.jira_service import disconnect, get_connection, save_connection, validate_connection

JIRA_TYPE, JIRA_URL, JIRA_IDENTITY, JIRA_CREDENTIAL, JIRA_PROJECT = range(5)


async def _jira_call(fn, *args, **kwargs):
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


async def jira_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type != "private":
        await update.effective_message.reply_text("⚠️ اتصال Jira را فقط در چت خصوصی با ربات انجام دهید.")
        return ConversationHandler.END
    context.user_data["jira_connect"] = {}
    await update.effective_message.reply_text("🔗 اتصال به Jira\n\nمرحله ۱ از ۵\nنوع Jira را ارسال کنید:\ncloud یا server\n\nبرای Jira Server/Data Center مقدار server را بفرستید.\nبرای لغو /cancel را بفرستید.")
    return JIRA_TYPE


async def jira_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip().lower()
    if value not in ("cloud", "server"):
        await update.effective_message.reply_text("❌ فقط cloud یا server را ارسال کنید:")
        return JIRA_TYPE
    context.user_data["jira_connect"]["deployment"] = value
    await update.effective_message.reply_text("مرحله ۲ از ۵\nآدرس Jira سازمان را ارسال کنید.\n\nCloud: https://company.atlassian.net\nServer/Data Center: https://jira.company.com")
    return JIRA_URL


async def jira_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip().rstrip("/")
    if not value.startswith("https://"):
        await update.effective_message.reply_text("❌ آدرس باید با https:// شروع شود. دوباره ارسال کنید:")
        return JIRA_URL
    context.user_data["jira_connect"]["url"] = value
    await update.effective_message.reply_text(
        "مرحله ۳ از ۵\n" + ("نام کاربری Jira را ارسال کنید." if context.user_data["jira_connect"]["deployment"] == "server" else "ایمیل حساب Atlassian خود را ارسال کنید:")
    )
    return JIRA_IDENTITY


async def jira_identity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip()
    deployment = context.user_data["jira_connect"]["deployment"]
    if not value or (deployment == "cloud" and "@" not in value):
        await update.effective_message.reply_text("❌ مقدار واردشده معتبر نیست. دوباره ارسال کنید:")
        return JIRA_IDENTITY
    context.user_data["jira_connect"]["identity"] = value
    await update.effective_message.reply_text(
        "مرحله ۴ از ۵\n" + (
            "Credential Jira Server را ارسال کنید. اگر نصب شما PAT دارد، PAT را وارد کنید؛ در غیر این صورت credential مورد استفاده برای Basic Authentication را وارد کنید.\n\n⚠️ فقط در چت خصوصی ارسال کنید؛ پیام حذف می‌شود."
            if deployment == "server" else
            "API Token Atlassian را ارسال کنید.\n\n⚠️ فقط در چت خصوصی ارسال کنید؛ پیام حذف می‌شود."
        )
    )
    return JIRA_CREDENTIAL


async def jira_credential(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip()
    if not value:
        await update.effective_message.reply_text("❌ Credential خالی است. دوباره ارسال کنید:")
        return JIRA_CREDENTIAL
    context.user_data["jira_connect"]["credential"] = value
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    await update.effective_message.reply_text("مرحله ۵ از ۵\nکلید پروژه Jira را ارسال کنید. مثال: PROJ")
    return JIRA_PROJECT


async def jira_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project = (update.effective_message.text or "").strip().upper()
    data = context.user_data.get("jira_connect", {})
    try:
        auth_method = "pat" if data.get("deployment") == "server" else "basic"
        myself = await _jira_call(validate_connection, data["url"], data["identity"], data["credential"], project, data["deployment"], auth_method)
        await _jira_call(save_connection, update.effective_user.id, data["url"], data["identity"], data["credential"], project, deployment=data["deployment"], account_id=str(myself.get("accountId") or ""))
        context.user_data.pop("jira_connect", None)
        label = "Jira Server / Data Center" if data["deployment"] == "server" else "Jira Cloud"
        await update.effective_message.reply_text(f"✅ اتصال {label} با موفقیت انجام شد.\n\nProject: {project}\n🔄 همگام‌سازی خودکار فعال شد.\nهر ۶۰ ثانیه تغییرات Jira و Telegram بررسی می‌شوند.")
    except Exception as exc:
        context.user_data.pop("jira_connect", None)
        await update.effective_message.reply_text(f"❌ اتصال برقرار نشد.\n\nجزئیات: {str(exc)[:500]}\n\nدوباره /jira را اجرا کنید.")
    return ConversationHandler.END


async def jira_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("jira_connect", None)
    await update.effective_message.reply_text("اتصال Jira لغو شد.")
    return ConversationHandler.END


async def jira_disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    disconnected = await _jira_call(disconnect, update.effective_user.id)
    await update.effective_message.reply_text("🔌 اتصال Jira قطع شد." if disconnected else "اتصال فعالی برای شما پیدا نشد.")


async def jira_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = await _jira_call(get_connection, update.effective_user.id)
    if not connection:
        await update.effective_message.reply_text("🔌 Jira به این ربات متصل نیست. برای اتصال /jira را اجرا کنید.")
        return
    label = "Jira Server / Data Center" if connection.get("deployment") == "server" else "Jira Cloud"
    await update.effective_message.reply_text(
        "🟢 Jira متصل است\n\n"
        f"نوع: {label}\nProject: {connection.get('project_key')}\nServer: {connection.get('base_url')}\n"
        f"آخرین Sync: {connection.get('last_sync_at') or 'هنوز اجرا نشده'}"
    )
