from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from services.web_app import get_web_app_url


def web_app_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🌐 باز کردن وب اپ",
                web_app=WebAppInfo(url=get_web_app_url()),
            )
        ]
    ])


async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "برای باز کردن نسخه وب/Telegram Mini App روی دکمه زیر بزنید:",
        reply_markup=web_app_keyboard(),
    )
