import asyncio
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.custom_bot_service import FEATURE_OPTIONS, create_custom_bot_request, validate_bot_token


async def _custom_bot_call(fn, *args, **kwargs):
    return await asyncio.to_thread(partial(fn, *args, **kwargs))


def _selected(context) -> list[str]:
    return context.user_data.setdefault("custom_bot_features", ["tasks", "teams", "reports", "search"])


def custom_bot_keyboard(context) -> InlineKeyboardMarkup:
    selected = set(_selected(context))
    rows = []
    for key, label in FEATURE_OPTIONS.items():
        mark = "✅" if key in selected else "▫️"
        rows.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"custombot_toggle_{key}")])
    rows.append([InlineKeyboardButton("🚀 ثبت و ساخت ربات اختصاصی", callback_data="custombot_submit")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="tasks_back")])
    return InlineKeyboardMarkup(rows)


async def show_custom_bot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 ساخت ربات اختصاصی\n\n"
        "توکن API رباتی را که از @BotFather گرفته‌اید به سیستم می‌دهید و قابلیت‌های دلخواه را انتخاب می‌کنید. "
        "در نسخه بتا این امکان رایگان است؛ بعداً ممکن است پلن‌های پولی برای آن فعال شود.\n\n"
        "1) امکانات مورد نیازتان را انتخاب کنید.\n"
        "2) روی ثبت بزنید.\n"
        "3) توکن Bot API را ارسال کنید.\n\n"
        "⚠️ توکن را فقط در همین مرحله ارسال کنید و پس از ثبت، برای امنیت در BotFather آن را مدیریت کنید."
    )
    message = update.callback_query.message if update.callback_query else update.message
    await message.reply_text(text, reply_markup=custom_bot_keyboard(context))


async def custom_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("custombot_toggle_"):
        feature = data.replace("custombot_toggle_", "", 1)
        selected = _selected(context)
        if feature in selected:
            selected.remove(feature)
        elif feature in FEATURE_OPTIONS:
            selected.append(feature)
        await query.message.reply_text("امکانات ربات اختصاصی را انتخاب کنید:", reply_markup=custom_bot_keyboard(context))
        return
    if data == "custombot_submit":
        context.user_data["step"] = "custom_bot_token"
        await query.message.reply_text(
            "🔐 لطفاً توکن Bot API ربات خود را ارسال کنید.\n"
            "نمونه فرمت: `123456789:AA...`\n\n"
            "بعد از ثبت، ربات اختصاصی شما با امکانات انتخاب‌شده در لیست فعال‌سازی قرار می‌گیرد.",
            parse_mode="Markdown",
        )


async def handle_custom_bot_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("step") != "custom_bot_token":
        return False
    token = (update.message.text or "").strip()
    if not await _custom_bot_call(validate_bot_token, token):
        await update.message.reply_text("⚠️ فرمت توکن معتبر نیست. لطفاً توکن Bot API دریافتی از @BotFather را دوباره ارسال کنید.")
        return True
    request = await _custom_bot_call(create_custom_bot_request, update.effective_user, token, _selected(context))
    context.user_data.pop("step", None)
    context.user_data.pop("custom_bot_features", None)
    await update.message.reply_text(
        "✅ ربات اختصاصی شما ثبت شد.\n\n"
        f"🆔 کد ربات: `{request['bot_key']}`\n"
        f"🎛 امکانات: {request['features']}\n"
        "💳 وضعیت هزینه: رایگان در نسخه بتا\n\n"
        "اگر سرویس به‌صورت چندرباته اجرا شود، این ربات پس از بارگذاری مجدد سرویس با همین تنظیمات فعال می‌شود.",
        parse_mode="Markdown",
    )
    return True
