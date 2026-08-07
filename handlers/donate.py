from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import ContextTypes

DONATION_AMOUNTS = (10, 40, 100)


def donate_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐️ {amount} استارز", callback_data=f"donate_{amount}")]
        for amount in DONATION_AMOUNTS
    ])


async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    await message.reply_text(
        "💙 حمایت از توسعه ربات\n\n"
        "برای دونیت با Telegram Stars یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=donate_keyboard(),
    )


async def donate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.replace("donate_", "", 1))
    if amount not in DONATION_AMOUNTS:
        await query.message.reply_text("⚠️ مبلغ انتخاب‌شده معتبر نیست.")
        return
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=f"دونیت {amount} استارز",
        description="حمایت از نگهداری و توسعه Task Manager Bot",
        payload=f"donation-stars-{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Telegram Stars", amount=amount)],
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("donation-stars-"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="پرداخت نامعتبر است.")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    if payment and payment.currency == "XTR":
        await update.message.reply_text(
            f"💙 از حمایت شما سپاسگزاریم!\n⭐️ {payment.total_amount} استارز دریافت شد."
        )
