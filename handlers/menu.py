from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from handlers.reports import show_reports_menu
from handlers.donate import DONATION_AMOUNTS
from handlers.templates import show_templates_menu
from handlers.integrations import show_integrations
from services.habit_service import get_user_habits
from services.task_service import get_all_user_tasks
from services.team_service import get_user_teams
from services.timezone_service import build_timezone_keyboard, build_timezone_text
from services.user_service import get_user_date_format, set_user_date_format, validate_timezone, set_user_timezone

def _bot_profile(context=None): return context.bot_data.get("bot_config") if context is not None else None
def _feature_enabled(profile, feature): return not feature or profile is None or profile.feature_enabled(feature)

def main_menu(context=None):
    profile=_bot_profile(context); menu_items=profile.menu if profile is not None else []
    if not menu_items:
        from bot_platform import DEFAULT_MENU; menu_items=DEFAULT_MENU
    if profile is None or menu_items == __import__("bot_platform").DEFAULT_MENU:
        rows=[[InlineKeyboardButton("➕ افزودن تسک",callback_data="add_task"),InlineKeyboardButton("📋 تسک‌ها",callback_data="tasks")],[InlineKeyboardButton("🌱 عادت من",callback_data="habit_menu"),InlineKeyboardButton("📊 گزارش",callback_data="stats"),InlineKeyboardButton("📖 راهنما",callback_data="help")],[InlineKeyboardButton("⚙️ تنظیمات",callback_data="settings"),InlineKeyboardButton("📞 ارتباط با ما",callback_data="contact_us")]]
        rows=[[b for b in row if not(b.callback_data=="habit_menu" and not _feature_enabled(profile,"habits"))] for row in rows]
        return InlineKeyboardMarkup([row for row in rows if row])
    return InlineKeyboardMarkup([[InlineKeyboardButton(item["label"],callback_data=item["callback_data"])] for item in menu_items if _feature_enabled(profile,item.get("feature"))])

def main_menu_summary(user_id):
    try: active_habits=len(get_user_habits(user_id,active_only=True))
    except Exception: active_habits=0
    try:
        tasks=get_all_user_tasks(user_id);in_progress=sum(1 for task in tasks if str(task.get("status") or "").lower() in {"in_progress","in progress","در حال انجام"})
    except Exception: in_progress=0
    try: shared_teams=len(get_user_teams(user_id))
    except Exception: shared_teams=0
    return f"📊 **خلاصه وضعیت**\n\n🔄 عادت‌های فعال: **{active_habits}**\n⚡ فعالیت‌های در حال انجام: **{in_progress}**\n👥 تیم‌های مشترک: **{shared_teams}**"

def add_task_options_keyboard(context=None):
    profile=_bot_profile(context);rows=[[InlineKeyboardButton("📝 ثبت تسک جدید",callback_data="add_task_manual")]]
    if _feature_enabled(profile,"bulk_import"): rows.append([InlineKeyboardButton("📥 ثبت گروهی",callback_data="import_bulk")])
    if _feature_enabled(profile,"ai"): rows.append([InlineKeyboardButton("🤖 ثبت با هوش مصنوعی",callback_data="ai_start")])
    if _feature_enabled(profile,"templates"): rows.append([InlineKeyboardButton("🧩 انتخاب از تمپلیت‌ها",callback_data="templates")])
    rows.append([InlineKeyboardButton("🔙 بازگشت",callback_data="tasks_back")]);return InlineKeyboardMarkup(rows)

async def show_add_task_menu(update, context):
    message=update.effective_message
    if message is None and update.callback_query:
        message=update.callback_query.message
    if message is None:
        return
    if update.callback_query:
        await update.callback_query.answer()
    await message.reply_text("➕ **افزودن تسک**\n\nروش ثبت تسک را انتخاب کنید:",reply_markup=add_task_options_keyboard(context),parse_mode="Markdown")

def tasks_options_keyboard(context=None):
    profile=_bot_profile(context)
    rows=[[InlineKeyboardButton("📋 لیست تسک‌های فعال",callback_data="tasks_list")],[InlineKeyboardButton("🕒 تاریخ ایجاد",callback_data="sort_created")],[InlineKeyboardButton("📅 بر اساس ددلاین",callback_data="sort_deadline")],[InlineKeyboardButton("🔙 بازگشت",callback_data="tasks_back")]]
    if _feature_enabled(profile,"search"): rows.insert(2,[InlineKeyboardButton("🔎 جستجو",callback_data="search")])
    return InlineKeyboardMarkup(rows)

def settings_keyboard(context=None):
    profile=_bot_profile(context);rows=[]
    if _feature_enabled(profile,"integrations"):rows.append([InlineKeyboardButton("🔗 اتصال به سرویس‌های مدیریت تسک",callback_data="integrations")])
    rows += [[InlineKeyboardButton("🌍 زمان محلی",callback_data="settings_timezone")],[InlineKeyboardButton("📅 نوع تاریخ",callback_data="settings_date_format")],[InlineKeyboardButton("🌐 تغییر زبان",callback_data="settings_language")]]
    if _feature_enabled(profile,"custom_bots"):rows.append([InlineKeyboardButton("🤖 ساخت ربات اختصاصی",callback_data="custom_bot")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی",callback_data="tasks_back")]);return InlineKeyboardMarkup(rows)
def timezone_keyboard(user_id):
    rows=build_timezone_keyboard(user_id,InlineKeyboardButton);rows.append([InlineKeyboardButton("🔙 بازگشت به تنظیمات",callback_data="settings")]);return InlineKeyboardMarkup(rows)
def timezone_text(user_id):return build_timezone_text(user_id)
def date_format_keyboard(user_id):
    current=get_user_date_format(user_id);jalali="✅ شمسی 🇮🇷" if current=="jalali" else "شمسی 🇮🇷";gregorian="✅ میلادی 🌐" if current=="gregorian" else "میلادی 🌐";return InlineKeyboardMarkup([[InlineKeyboardButton(jalali,callback_data="date_format_jalali")],[InlineKeyboardButton(gregorian,callback_data="date_format_gregorian")],[InlineKeyboardButton("🔙 بازگشت به تنظیمات",callback_data="settings")]])
def date_format_text(user_id):
    current=get_user_date_format(user_id);label="شمسی 🇮🇷" if current=="jalali" else "میلادی 🌐";return f"🗓 **تنظیمات تقویم**\n\nتقویم فعال: **{label}**"
def language_keyboard():return InlineKeyboardMarkup([[InlineKeyboardButton("🇮🇷 فارسی",callback_data="language_fa")],[InlineKeyboardButton("🇬🇧 English",callback_data="language_en")],[InlineKeyboardButton("🔙 بازگشت به تنظیمات",callback_data="settings")]])
def contact_text():return "📞 **ارتباط با ما**\nبرای پیشنهاد یا پشتیبانی با ما در ارتباط باشید."
def contact_keyboard():
    rows=[[InlineKeyboardButton(f"⭐️ دونیت {amount} استارز",callback_data=f"donate_{amount}")] for amount in DONATION_AMOUNTS];rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی",callback_data="tasks_back")]);return InlineKeyboardMarkup(rows)

async def button_handler(update,context):
    query=update.callback_query;data=query.data
    if data=="report_calendar_pdf":
        from handlers.calendar_pdf import calendar_pdf_callback;return await calendar_pdf_callback(update,context)
    if data.startswith("report_"):
        from handlers.reports import reports_callback;return await reports_callback(update,context)
    if data.startswith(("ai_task_","ai_habit_")):
        from handlers.ai import ai_habit_callback,ai_task_callback
        return await (ai_habit_callback(update,context) if data.startswith("ai_habit_") else ai_task_callback(update,context))
    if data=="ai_menu":
        profile=_bot_profile(context)
        if not _feature_enabled(profile,"ai"):
            await query.answer("هوش مصنوعی برای این ربات فعال نیست.",show_alert=True);return
        from handlers.ai import ai_command
        await query.answer()
        return await ai_command(update,context)
    if data.startswith("habit_"):
        from handlers.habits import handle_habit_callback;return await handle_habit_callback(update,context)
    profile=_bot_profile(context);feature_by_callback={"add_task":"tasks","tasks":"tasks","teams":"teams","templates":"templates","habit_menu":"habits","stats":"reports","import_bulk":"bulk_import","custom_bot":"custom_bots","search":"search"};feature=feature_by_callback.get(data)
    if feature and not _feature_enabled(profile,feature):await query.answer("این قابلیت برای این ربات فعال نیست.",show_alert=True);return
    await query.answer()
    if data=="add_task":return await show_add_task_menu(update,context)
    if data=="add_task_manual":
        from handlers.task import add_task;return await add_task(update,context)
    if data=="ai_start":
        from handlers.ai import _ai_examples_text,_ai_examples_keyboard;return await query.message.reply_text(_ai_examples_text(),reply_markup=_ai_examples_keyboard(),parse_mode="Markdown")
    if data=="tasks":return await query.message.reply_text("📝 **تسک‌های من**",reply_markup=tasks_options_keyboard(context),parse_mode="Markdown")
    if data=="tasks_list":
        from handlers.task_pagination import paginated_list_tasks;return await paginated_list_tasks(update,context)
    if data=="search":return await query.message.reply_text("🔎 عبارت مورد نظر را برای جستجو در تسک‌ها ارسال کنید:")
    if data=="teams":
        from handlers.team import team_command;return await team_command(update,context)
    if data=="templates":return await show_templates_menu(update,context)
    if data=="habit_menu":
        from handlers.habits import show_habit_menu;return await show_habit_menu(update,context)
    if data=="stats":return await show_reports_menu(update,context)
    if data=="help":
        from handlers.help import help_command;return await help_command(update,context)
    if data=="settings":return await query.message.reply_text("⚙️ **تنظیمات**",reply_markup=settings_keyboard(context),parse_mode="Markdown")
    if data=="settings_timezone":return await query.message.reply_text(timezone_text(update.effective_user.id),reply_markup=timezone_keyboard(update.effective_user.id),parse_mode="Markdown")
    if data=="settings_date_format":return await query.message.reply_text(date_format_text(update.effective_user.id),reply_markup=date_format_keyboard(update.effective_user.id),parse_mode="Markdown")
    if data=="settings_language":return await query.message.reply_text("🌐 **زبان**",reply_markup=language_keyboard(),parse_mode="Markdown")
    if data.startswith("timezone_set_"):
        tz_name=data[len("timezone_set_"):]
        if not validate_timezone(tz_name):await query.answer("منطقه زمانی نامعتبر است.",show_alert=True);return
        if not set_user_timezone(update.effective_user.id,tz_name):await query.answer("ذخیره منطقه زمانی انجام نشد.",show_alert=True);return
        await query.answer("منطقه زمانی ذخیره شد.");return await query.message.edit_text(timezone_text(update.effective_user.id),reply_markup=timezone_keyboard(update.effective_user.id),parse_mode="Markdown")
    if data in {"date_format_jalali","date_format_gregorian"}:set_user_date_format(update.effective_user.id,"jalali" if data.endswith("jalali") else "gregorian");return await query.message.reply_text(date_format_text(update.effective_user.id),reply_markup=date_format_keyboard(update.effective_user.id),parse_mode="Markdown")
    if data in {"language_fa","language_en"}:await query.answer("زبان فارسی برای این ربات فعال است.",show_alert=True);return
    if data=="integrations":return await show_integrations(update,context)
    if data=="custom_bot":
        from handlers.custom_bot import custom_bot_callback;return await custom_bot_callback(update,context)
    if data=="import_bulk":
        from handlers.import_bulk import import_callback;return await import_callback(update,context)
    if data=="download_csv":
        from handlers.task import download_csv;return await download_csv(update,context)
    if data=="contact_us":return await query.message.reply_text(contact_text(),reply_markup=contact_keyboard(),parse_mode="Markdown")
