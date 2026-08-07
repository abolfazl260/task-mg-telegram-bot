from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from config import WEB_APP_URL


def web_app_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🌐 باز کردن وب اپ",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        ]
    ])


async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای باز کردن نسخه وب/Telegram Mini App روی دکمه زیر بزنید:",
        reply_markup=web_app_keyboard(),
    )
