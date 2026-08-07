from datetime import date, datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.habit_service import (
    TEMPLATES, create_habit, delete_habit, get_habit, get_logs,
    get_user_habits, is_habit_due_on, mark_done, stats_for_habit, update_habit,
)

REPEAT_LABEL = {"daily": "روزانه", "weekly": "هفتگی", "monthly": "ماهانه"}
DAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
BACK_TO_HABITS_BUTTON = InlineKeyboardButton("🔙 بازگشت به عادت‌ها", callback_data="habit_list")


def habit_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ایجاد عادت", callback_data="habit_create")],
        [InlineKeyboardButton("📋 عادت‌های من", callback_data="habit_list")],
        [InlineKeyboardButton("✅ ثبت انجام امروز", callback_data="habit_today")],
        [InlineKeyboardButton("🔥 رکوردهای من", callback_data="habit_records")],
        [InlineKeyboardButton("📊 داشبورد", callback_data="habit_dashboard")],
        [InlineKeyboardButton("⏰ تنظیم یادآوری", callback_data="habit_reminders")],
    ])


def _create_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ایجاد عادت جدید", callback_data="habit_new")],
        [InlineKeyboardButton("انتخاب از قالب آماده", callback_data="habit_templates")],
        [BACK_TO_HABITS_BUTTON],
    ])


def _habit_buttons(habits, prefix):
    return InlineKeyboardMarkup([[InlineKeyboardButton(h["title"], callback_data=f"{prefix}_{h['id']}")] for h in habits])


def _reminder_keyboard(habit_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("۰۷:۰۰ صبح", callback_data=f"habit_remtime_{habit_id}_07:00")],
        [InlineKeyboardButton("۰۹:۰۰ صبح", callback_data=f"habit_remtime_{habit_id}_09:00")],
        [InlineKeyboardButton("۱۱:۰۰ ظهر", callback_data=f"habit_remtime_{habit_id}_11:00")],
        [InlineKeyboardButton("۱۸:۰۰ عصر", callback_data=f"habit_remtime_{habit_id}_18:00")],
        [InlineKeyboardButton("۲۱:۰۰ شب", callback_data=f"habit_remtime_{habit_id}_21:00")],
        [InlineKeyboardButton("بدون یادآوری", callback_data=f"habit_remtime_{habit_id}_none")],
        [BACK_TO_HABITS_BUTTON],
    ])


def reminder_label(habit):
    reminder_time = habit.get("reminder_time")
    repeat = REPEAT_LABEL.get(habit.get("repeat_type"), "روزانه")
    if not reminder_time:
        return "بدون یادآوری"
    if habit.get("repeat_type") == "weekly":
        return f"{repeat} در روز شروع عادت، ساعت {reminder_time}"
    if habit.get("repeat_type") == "monthly":
        return f"{repeat} در تاریخ روز شروع عادت، ساعت {reminder_time}"
    return f"{repeat} ساعت {reminder_time}"


def format_template(tpl):
    return (
        f"🌱 {tpl.get('title', '—')}\n\n"
        f"📂 دسته‌بندی: {tpl.get('category') or '—'}\n"
        f"🎯 هدف: {tpl.get('target') or '—'}\n"
        f"🔁 برنامه تکرار: {REPEAT_LABEL.get(tpl.get('repeat_type'), 'روزانه')}\n"
        f"⏰ یادآوری پیشنهادی: {tpl.get('reminder_time') or 'بدون یادآوری'}\n\n"
        f"چرا این عادت را اضافه کنم؟\n{tpl.get('description') or '—'}\n\n"
        "اگر این قالب را فعال کنید، همین تنظیمات برای شما ثبت می‌شود."
    )


def format_habit(habit):
    st = stats_for_habit(habit)
    active = "فعال" if habit.get("active") == "1" else "غیرفعال"
    return (
        f"🌱 {habit.get('title','—')}\n\n"
        f"📂 دسته‌بندی: {habit.get('category') or '—'}\n"
        f"🔁 تکرار: {REPEAT_LABEL.get(habit.get('repeat_type'), 'روزانه')}\n"
        f"🎯 هدف: {habit.get('target') or '—'}\n"
        f"⏰ یادآوری: {reminder_label(habit)}\n"
        f"📅 شروع: {habit.get('start_date') or '—'}\n"
        f"📌 وضعیت: {active}\n\n"
        f"🔥 زنجیره فعلی: {st['current']} روز\n"
        f"🏆 بهترین رکورد: {st['best']} روز\n"
        f"✅ تعداد انجام: {st['total']} بار\n"
        f"🕐 آخرین انجام: {st['last']}"
    )


async def show_habit_menu(update, context):
    msg = update.effective_message
    await msg.reply_text("🌱 مدیریت عادت‌ها", reply_markup=habit_menu_keyboard())


async def handle_habit_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "habit_menu":
        await show_habit_menu(update, context)
    elif data == "habit_create":
        await query.message.reply_text("🌱 ایجاد عادت\n\n1. ایجاد عادت جدید\n2. انتخاب از قالب آماده", reply_markup=_create_keyboard())
    elif data == "habit_new":
        context.user_data["habit_step"] = "title"
        context.user_data["new_habit"] = {}
        await query.message.reply_text("عنوان عادت را وارد کنید:")
    elif data == "habit_templates":
        kb = [[InlineKeyboardButton(t["title"], callback_data=f"habit_tpl_view_{t['key']}")] for t in TEMPLATES]
        kb.append([BACK_TO_HABITS_BUTTON])
        await query.message.reply_text("یک قالب آماده انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("habit_tpl_view_"):
        tpl = next(t for t in TEMPLATES if t["key"] == data.replace("habit_tpl_view_", ""))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ فعال‌سازی این عادت", callback_data=f"habit_tpl_create_{tpl['key']}")],
            [InlineKeyboardButton("🔙 بازگشت به قالب‌ها", callback_data="habit_templates")],
            [BACK_TO_HABITS_BUTTON],
        ])
        await query.message.reply_text(format_template(tpl), reply_markup=kb)
    elif data.startswith("habit_tpl_create_"):
        tpl = next(t for t in TEMPLATES if t["key"] == data.replace("habit_tpl_create_", ""))
        hid = create_habit(
            user_id,
            tpl["title"],
            tpl["category"],
            tpl["description"],
            tpl.get("repeat_type", "daily"),
            tpl["target"],
            tpl.get("reminder_time", ""),
            date.today().isoformat(),
        )
        await query.message.reply_text(f"✅ عادت فعال شد\n🆔 {hid}\n\n{format_habit(get_habit(hid))}")
    elif data == "habit_list":
        habits = get_user_habits(user_id)
        if not habits:
            await query.message.reply_text("هنوز عادتی ثبت نشده است.")
            return
        for h in habits:
            toggle_label = "غیرفعال کردن عادت" if h.get("active") == "1" else "فعال کردن عادت"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ ویرایش", callback_data=f"habit_edit_{h['id']}"), InlineKeyboardButton("🗑 حذف", callback_data=f"habit_del_{h['id']}")],
                [InlineKeyboardButton(toggle_label, callback_data=f"habit_toggle_{h['id']}")],
                [BACK_TO_HABITS_BUTTON],
            ])
            await query.message.reply_text(format_habit(h), reply_markup=kb)
    elif data == "habit_today":
        habits = [h for h in get_user_habits(user_id, active_only=True) if is_habit_due_on(h)]
        if not habits:
            await query.message.reply_text("برای امروز عادت فعالی ندارید.")
            return
        await query.message.reply_text("🌱 عادت‌های امروز\n\nکدام مورد انجام شد؟", reply_markup=_habit_buttons(habits, "habit_done"))
    elif data.startswith("habit_done_"):
        hid = data.replace("habit_done_", "")
        mark_done(hid, user_id)
        st = stats_for_habit(get_habit(hid))
        await query.message.reply_text(f"✅ ثبت شد\n\nآفرین!\n\n🔥 زنجیره فعلی:\n{st['current']} روز\n\n🏆 بهترین رکورد:\n{st['best']} روز")
    elif data == "habit_records":
        habits = get_user_habits(user_id)
        text = "🔥 رکوردهای من\n\n" + "\n\n".join(format_habit(h) for h in habits) if habits else "رکوردی وجود ندارد."
        await query.message.reply_text(text)
    elif data == "habit_dashboard":
        await query.message.reply_text(build_dashboard(user_id))
    elif data == "habit_reminders":
        habits = get_user_habits(user_id, active_only=True)
        await query.message.reply_text(
            "⏰ عادت را برای تنظیم یادآوری انتخاب کنید.\n\n"
            "یادآوری بر اساس تکرار خود عادت ارسال می‌شود: روزانه هر روز، هفتگی در روز شروع عادت، و ماهانه در تاریخ روز شروع عادت.",
            reply_markup=_habit_buttons(habits, "habit_rempick") if habits else InlineKeyboardMarkup([[BACK_TO_HABITS_BUTTON]]),
        )
    elif data.startswith("habit_rempick_"):
        hid = data.replace("habit_rempick_", "")
        h = get_habit(hid)
        await query.message.reply_text(
            f"⏰ زمان یادآوری\n\nبرنامه فعلی: {reminder_label(h)}\n"
            "یک ساعت را انتخاب کنید یا یادآوری را خاموش کنید:",
            reply_markup=_reminder_keyboard(hid),
        )
    elif data.startswith("habit_remtime_"):
        _, _, hid, value = data.split("_", 3)
        update_habit(hid, reminder_time="" if value == "none" else value)
        await query.message.reply_text(f"✅ زمان یادآوری ذخیره شد.\n\n{format_habit(get_habit(hid))}")
    elif data.startswith("habit_toggle_"):
        hid = data.replace("habit_toggle_", "")
        h = get_habit(hid)
        if h and h.get("user_id") == str(user_id):
            new_active = "0" if h.get("active") == "1" else "1"
            update_habit(hid, active=new_active)
            status = "فعال شد" if new_active == "1" else "غیرفعال شد"
            await query.message.reply_text(f"✅ عادت {status}.\n\n{format_habit(get_habit(hid))}")
    elif data.startswith("habit_del_"):
        hid = data.replace("habit_del_", "")
        h = get_habit(hid)
        if h and h.get("user_id") == str(user_id):
            delete_habit(hid)
            await query.message.reply_text("✅ عادت حذف شد.")
    elif data.startswith("habit_edit_"):
        hid = data.replace("habit_edit_", "")
        context.user_data["habit_edit_id"] = hid
        context.user_data["habit_step"] = "edit_title"
        await query.message.reply_text("عنوان جدید عادت را وارد کنید:")


async def handle_habit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("habit_step")
    if not step:
        return False
    text = update.message.text.strip()
    h = context.user_data.setdefault("new_habit", {})
    if step == "title":
        h["title"] = text; context.user_data["habit_step"] = "category"; await update.message.reply_text("دسته‌بندی را وارد کنید:"); return True
    if step == "category":
        h["category"] = text; context.user_data["habit_step"] = "description"; await update.message.reply_text("توضیحات را وارد کنید یا /skip بزنید:"); return True
    if step == "description":
        h["description"] = text; context.user_data["habit_step"] = "repeat_type"; await update.message.reply_text("نوع تکرار را وارد کنید: روزانه، هفتگی یا ماهانه"); return True
    if step == "repeat_type":
        h["repeat_type"] = {"روزانه": "daily", "هفتگی": "weekly", "ماهانه": "monthly"}.get(text, "daily"); context.user_data["habit_step"] = "target"; await update.message.reply_text("هدف مورد نظر را وارد کنید:"); return True
    if step == "target":
        h["target"] = text; context.user_data["habit_step"] = "reminder_time"; await update.message.reply_text("زمان یادآوری را به شکل 07:00 یا 21:00 وارد کنید؛ برای نداشتن یادآوری /skip بزنید:"); return True
    if step == "reminder_time":
        h["reminder_time"] = text; context.user_data["habit_step"] = "start_date"; await update.message.reply_text("تاریخ شروع را به شکل 2026-08-07 وارد کنید؛ برای امروز /skip بزنید:"); return True
    if step == "start_date":
        h["start_date"] = text
        hid = create_habit(update.effective_user.id, h["title"], h.get("category", ""), h.get("description", ""), h.get("repeat_type", "daily"), h.get("target", ""), h.get("reminder_time", ""), h.get("start_date", ""))
        context.user_data.pop("habit_step", None); context.user_data.pop("new_habit", None)
        await update.message.reply_text(f"✅ عادت ثبت شد\n🆔 {hid}"); return True
    if step == "edit_title":
        update_habit(context.user_data.get("habit_edit_id"), title=text)
        context.user_data.pop("habit_step", None); context.user_data.pop("habit_edit_id", None)
        await update.message.reply_text("✅ عادت ویرایش شد."); return True
    return False


async def habit_skip(update, context):
    step = context.user_data.get("habit_step")
    h = context.user_data.setdefault("new_habit", {})
    if step == "description":
        h["description"] = ""; context.user_data["habit_step"] = "repeat_type"; await update.message.reply_text("نوع تکرار را وارد کنید: روزانه، هفتگی یا ماهانه"); return True
    if step == "reminder_time":
        h["reminder_time"] = ""; context.user_data["habit_step"] = "start_date"; await update.message.reply_text("تاریخ شروع را به شکل 2026-08-07 وارد کنید؛ برای امروز /skip بزنید:"); return True
    if step == "start_date":
        h["start_date"] = date.today().isoformat()
        hid = create_habit(update.effective_user.id, h["title"], h.get("category", ""), h.get("description", ""), h.get("repeat_type", "daily"), h.get("target", ""), h.get("reminder_time", ""), h["start_date"])
        context.user_data.pop("habit_step", None); context.user_data.pop("new_habit", None)
        await update.message.reply_text(f"✅ عادت ثبت شد\n🆔 {hid}"); return True
    return False


def build_dashboard(user_id):
    habits = get_user_habits(user_id, active_only=True)
    logs = get_logs(user_id=user_id)
    today = date.today().isoformat()
    done_today = {l["habit_id"] for l in logs if l.get("done_date") == today}
    best = sorted([(stats_for_habit(h)["best"], h["title"]) for h in habits], reverse=True)
    week_start = date.today() - timedelta(days=6)
    lines = ["📊 داشبورد عادت‌ها\n", f"تعداد عادت فعال:\n{len(habits)}\n", f"عملکرد امروز:\n{len(done_today)} از {len(habits)} انجام شده\n"]
    lines.append("🔥 بهترین زنجیره:\n")
    lines.append(f"{best[0][1]}:\n{best[0][0]} روز\n" if best else "—\n")
    lines.append("📈 عملکرد هفته:\n")
    total_expected = len(habits) * 7
    total_done = 0
    for i in range(7):
        d = week_start + timedelta(days=i)
        count = len({l["habit_id"] for l in logs if l.get("done_date") == d.isoformat()})
        total_done += count
        lines.append(f"{DAYS_FA[d.weekday()]}:\n{'█' * count or '—'}")
    percent = round((total_done / total_expected) * 100) if total_expected else 0
    lines.append(f"\nدرصد موفقیت هفته:\n{percent}%")
    return "\n".join(lines)
