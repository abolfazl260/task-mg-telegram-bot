from telegram import Update
from telegram.ext import ContextTypes
from services.admin_access import create_admin_link
from services.permission_service import is_admin

async def backoffice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_admin(user.id):
        await update.effective_message.reply_text("🔐 لینک ورود به پنل مدیریت (۱۰ دقیقه معتبر):\n\n" + create_admin_link(user.id))
