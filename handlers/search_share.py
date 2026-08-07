from collections import defaultdict

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


def _format_task_list(tasks, title: str) -> str:
    tasks = sorted(tasks, key=lambda t: t.get("deadline") or "9999-99-99")
    lines = [f"{title}\n", f"تعداد: {len(tasks)}\n"]
    for i, t in enumerate(tasks, start=1):
        pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(t.get("priority"), "🟢")
        st = {"pending": "⏳", "in_progress": "🚀"}.get(t.get("status"), "⏳")
        lines.append(
            f"{i}. {pr} {st} {t.get('title', '-')}\n"
            f"   📅 {t.get('deadline') or 'بدون ددلاین'} | 📂 {t.get('category') or '—'}"
        )
    return "\n".join(lines)


async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /share — خروجی قابل فوروارد از تسک‌های فعال
    /share <user_id> — ارسال همان لیست به کاربر دیگر
    /share category — شروع اشتراک‌گذاری یک دسته
    /share category <نام‌دسته> [user_id]
    """

    args = context.args or []

    # /share category  or  /share category <name> [uid]
    if args and args[0].lower() in ("category", "cat", "دسته"):
        await _share_category_flow(update, context, args[1:])
        return

    tasks = get_active_tasks(update.effective_user.id)

    if not tasks:
        await update.message.reply_text("تسک فعالی برای اشتراک‌گذاری ندارید.")
        return

    name = update.effective_user.first_name or "کاربر"
    text = _format_task_list(tasks, f"📋 لیست تسک‌های فعال — {name}")

    target = None
    if args:
        try:
            target = int(args[0])
        except ValueError:
            await update.message.reply_text(
                "فرمت:\n"
                "• /share\n"
                "• /share <user_id>\n"
                "• /share category\n"
                "• /share category <نام‌دسته> [user_id]"
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
        "برای ارسال مستقیم: /share <user_id>\n"
        "برای اشتراک یک دسته: /share category"
    )


async def _share_category_flow(update, context, args):
    """Share tasks of one category."""

    tasks = get_active_tasks(update.effective_user.id)
    if not tasks:
        await update.message.reply_text("تسک فعالی ندارید.")
        return

    groups = defaultdict(list)
    for t in tasks:
        cat = (t.get("category") or "").strip() or "بدون دسته‌بندی"
        groups[cat].append(t)

    # no category name yet → show buttons
    if not args:
        buttons = []
        for cat in sorted(groups.keys(), key=lambda c: (-len(groups[c]), c))[:20]:
            buttons.append([
                InlineKeyboardButton(
                    f"📂 {cat} ({len(groups[cat])})",
                    callback_data=f"share_cat_{cat[:40]}",
                )
            ])
        if not buttons:
            await update.message.reply_text("دسته‌ای برای اشتراک نیست.")
            return
        await update.message.reply_text(
            "کدام دسته‌بندی را می‌خواهید اشتراک بگذارید؟",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # category name given
    cat_name = args[0]
    target = None
    if len(args) >= 2:
        try:
            target = int(args[1])
        except ValueError:
            pass

    # fuzzy match category
    matched = None
    for c in groups:
        if c == cat_name or cat_name.lower() in c.lower():
            matched = c
            break

    if not matched:
        await update.message.reply_text(
            f"دسته‌بندی «{cat_name}» پیدا نشد.\n"
            f"دسته‌های موجود: {', '.join(sorted(groups.keys())[:10])}"
        )
        return

    name = update.effective_user.first_name or "کاربر"
    text = _format_task_list(
        groups[matched],
        f"📂 دسته «{matched}» — اشتراک از {name}",
    )

    if target:
        try:
            await context.bot.send_message(
                chat_id=target,
                text=f"📨 {text}",
            )
            await update.message.reply_text(
                f"✅ دسته «{matched}» برای کاربر `{target}` ارسال شد.",
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(
                "ارسال نشد. طرف مقابل باید حداقل یک‌بار ربات را /start کرده باشد."
            )
        return

    await update.message.reply_text(
        text + f"\n\n💡 برای ارسال مستقیم:\n/share category {matched} <user_id>"
    )


async def share_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button: share_cat_<category>"."""

    query = update.callback_query
    await query.answer()

    cat_prefix = query.data.replace("share_cat_", "", 1)
    tasks = get_active_tasks(update.effective_user.id)
    groups = defaultdict(list)
    for t in tasks:
        cat = (t.get("category") or "").strip() or "بدون دسته‌بندی"
        groups[cat].append(t)

    matched = None
    for c in groups:
        if c.startswith(cat_prefix) or cat_prefix in c:
            matched = c
            break

    if not matched:
        await query.message.reply_text("دسته‌بندی پیدا نشد.")
        return

    name = update.effective_user.first_name or "کاربر"
    text = _format_task_list(
        groups[matched],
        f"📂 دسته «{matched}» — اشتراک از {name}",
    )

    await query.message.reply_text(
        text
        + "\n\n💡 این پیام را می‌توانید فوروارد کنید."
    )
