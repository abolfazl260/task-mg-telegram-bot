from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.task_service import search_tasks, get_active_tasks


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search <متن> — جستجو در عنوان، دسته، تگ و توضیح"""

    query = " ".join(context.args).strip() if context.args else ""

    if not query:
        context.user_data["step"] = "search_query"
        await update.message.reply_text(
            "🔍 عبارت جستجو را وارد کنید:\n(یا دوباره: /search کلمه)"
        )
        return

    await _run_search(update, context, query)


async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if consumed as search input."""

    if context.user_data.get("step") != "search_query":
        return False

    query = (update.message.text or "").strip()
    context.user_data.pop("step", None)

    if not query:
        await update.message.reply_text("عبارت خالی بود.")
        return True

    await _run_search(update, context, query)
    return True


async def _run_search(update, context, query: str):

    results = search_tasks(update.effective_user.id, query)

    if not results:
        await update.message.reply_text(f"نتیجه‌ای برای «{query}» پیدا نشد.")
        return

    lines = [f"🔍 نتایج جستجو برای «{query}» — {len(results)} مورد:\n"]

    for i, t in enumerate(results[:20], start=1):
        st = {"pending": "⏳", "in_progress": "🚀", "done": "✅", "cancelled": "❌"}.get(
            t.get("status"), ""
        )
        pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(t.get("priority"), "")
        lines.append(
            f"{i}. {pr}{st} {t.get('title', '-')} "
            f"| {t.get('deadline') or '—'} | `{t.get('id')}`"
        )

    if len(results) > 20:
        lines.append(f"\n... و {len(results) - 20} مورد دیگر")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /share — خروجی قابل فوروارد از تسک‌های فعال
    /share <user_id> — ارسال همان لیست به کاربر دیگر (باید قبلاً با ربات استارت کرده باشد)
    """

    tasks = get_active_tasks(update.effective_user.id)

    if not tasks:
        await update.message.reply_text("تسک فعالی برای اشتراک‌گذاری ندارید.")
        return

    tasks = sorted(tasks, key=lambda t: t.get("deadline") or "9999-99-99")

    name = update.effective_user.first_name or "کاربر"
    lines = [
        f"📋 لیست تسک‌های فعال — {name}\n",
        f"تعداد: {len(tasks)}\n",
    ]

    for i, t in enumerate(tasks, start=1):
        pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(t.get("priority"), "🟢")
        st = {"pending": "⏳", "in_progress": "🚀"}.get(t.get("status"), "⏳")
        lines.append(
            f"{i}. {pr} {st} {t.get('title', '-')}\n"
            f"   📅 {t.get('deadline') or 'بدون ددلاین'} | 📂 {t.get('category') or '—'}"
        )

    text = "\n".join(lines)

    target = None
    if context.args:
        try:
            target = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "فرمت: /share یا /share <user_id عددی>"
            )
            return

    if target:
        try:
            await context.bot.send_message(
                chat_id=target,
                text=f"📨 لیست اشتراک‌گذاری‌شده از طرف {name}:\n\n{text}",
            )
            await update.message.reply_text(
                f"✅ لیست برای کاربر `{target}` ارسال شد.",
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(
                "ارسال نشد. طرف مقابل باید حداقل یک‌بار ربات را /start کرده باشد."
            )
        return

    await update.message.reply_text(
        text + "\n\n💡 این پیام را می‌توانید فوروارد کنید.\n"
        "برای ارسال مستقیم: /share <user_id>"
    )
