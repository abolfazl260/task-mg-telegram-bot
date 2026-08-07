from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from services.jira_service import disconnect, get_connection, save_connection, validate_connection

JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT = range(4)


async def jira_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["jira_connect"] = {}
    await update.effective_message.reply_text(
        "🔗 اتصال به Jira\n\n"
        "مرحله ۱ از ۴\n"
        "آدرس Jira سازمان را ارسال کنید.\n\n"
        "مثال:\nhttps://company.atlassian.net\n\n"
        "برای لغو /cancel را بفرستید."
    )
    return JIRA_URL


async def jira_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip().rstrip("/")
    if not value.startswith("https://"):
        await update.effective_message.reply_text("❌ آدرس باید با https:// شروع شود. دوباره ارسال کنید:")
        return JIRA_URL
    context.user_data["jira_connect"]["url"] = value
    await update.effective_message.reply_text("مرحله ۲ از ۴\nایمیل حساب Jira خود را ارسال کنید:")
    return JIRA_EMAIL


async def jira_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip()
    if "@" not in value:
        await update.effective_message.reply_text("❌ ایمیل معتبر نیست. دوباره ارسال کنید:")
        return JIRA_EMAIL
    context.user_data["jira_connect"]["email"] = value
    await update.effective_message.reply_text(
        "مرحله ۳ از ۴\n"
        "API Token Jira را ارسال کنید.\n\n"
        "⚠️ توکن را فقط در چت خصوصی با ربات ارسال کنید. پس از دریافت، پیام توکن حذف می‌شود."
    )
    return JIRA_TOKEN


async def jira_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = (update.effective_message.text or "").strip()
    if not value:
        await update.effective_message.reply_text("❌ API Token خالی است. دوباره ارسال کنید:")
        return JIRA_TOKEN
    context.user_data["jira_connect"]["token"] = value
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    await update.effective_message.reply_text("مرحله ۴ از ۴\nکلید پروژه Jira را ارسال کنید. مثال: PROJ")
    return JIRA_PROJECT


async def jira_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project = (update.effective_message.text or "").strip().upper()
    data = context.user_data.get("jira_connect", {})
    try:
        validate_connection(data["url"], data["email"], data["token"], project)
        save_connection(update.effective_user.id, data["url"], data["email"], data["token"], project)
        context.user_data.pop("jira_connect", None)
        await update.effective_message.reply_text(
            f"✅ اتصال Jira با موفقیت انجام شد.\n\n"
            f"Project: {project}\n"
            "🔄 همگام‌سازی خودکار فعال شد.\n"
            "هر ۶۰ ثانیه تغییرات Jira و Telegram بررسی می‌شوند."
        )
    except Exception as exc:
        context.user_data.pop("jira_connect", None)
        await update.effective_message.reply_text(f"❌ اتصال برقرار نشد.\n\nجزئیات: {str(exc)[:500]}\n\nدوباره /jira را اجرا کنید.")
    return ConversationHandler.END


async def jira_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("jira_connect", None)
    await update.effective_message.reply_text("اتصال Jira لغو شد.")
    return ConversationHandler.END


async def jira_disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if disconnect(update.effective_user.id):
        await update.effective_message.reply_text("🔌 اتصال Jira قطع شد.")
    else:
        await update.effective_message.reply_text("اتصال فعالی برای شما پیدا نشد.")


async def jira_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = get_connection(update.effective_user.id)
    if not connection:
        await update.effective_message.reply_text("🔌 Jira به این ربات متصل نیست. برای اتصال /jira را اجرا کنید.")
        return
    await update.effective_message.reply_text(
        "🟢 Jira متصل است\n\n"
        f"Project: {connection.get('project_key')}\n"
        f"Server: {connection.get('base_url')}\n"
        f"آخرین Sync: {connection.get('last_sync_at') or 'هنوز اجرا نشده'}"
    )
