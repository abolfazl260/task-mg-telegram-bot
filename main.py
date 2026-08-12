import asyncio
import logging
import os
from datetime import time as dt_time
from telegram import BotCommand, Update, InlineKeyboardButton
from telegram.request import HTTPXRequest
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler, PreCheckoutQueryHandler, TypeHandler, ConversationHandler, filters)
from config import ADMIN_REPORT_TIME, BOT_PROFILES
from bot_platform import run_applications
from bot_context import set_current_bot_key
from handlers.start import start
from handlers.menu import button_handler
from handlers.integrations import integration_callback
from handlers.task import (add_task, save_task, list_tasks, priority_selected, deadline_selected, optional_field_callback, detail_page, download_csv, start_task, done_task, cancel_task, pending_task, sort_tasks_callback, assignment_callback, unassigned_tasks, take_assignment, take_confirm, assignment_manage_callback, task_details_callback, comment_callback, comment_cancel_callback)
from handlers.task_pagination import paginated_list_tasks, paginated_detail_page, paginated_sort_callback
from handlers.reports import show_reports_menu, reports_callback
from handlers.templates import show_templates_menu, templates_callback
from handlers.search_share import search_command, share_category_callback
from handlers.extra_reports import report_compare_months, report_performance, report_progress_bar
from handlers.import_bulk import import_callback
from handlers.team import team_command, team_callback
from services.reminders import morning_today_tasks, midday_summary_and_weekly, habit_reminders, weekly_habit_reports
from services.user_service import record_user
from services.sync_scheduler import run_external_sync, run_jira_sync
from handlers.custom_bot import custom_bot_callback
from services.admin_service import notify_new_user, daily_admin_report, error_handler
from handlers.habits import handle_habit_callback, show_habit_menu
from handlers.donate import donate_callback, donate_command, precheckout_callback, successful_payment_callback
from handlers.guest import handle_guest_task
from handlers.ai import ai_command
from handlers.business import handle_business_connection, handle_business_message, handle_deleted_business_messages, handle_edited_business_message
from handlers.jira import jira_start, jira_type, jira_url, jira_identity, jira_credential, jira_project, jira_cancel, jira_disconnect_command, jira_status_command, JIRA_TYPE, JIRA_URL, JIRA_IDENTITY, JIRA_CREDENTIAL, JIRA_PROJECT
from handlers.tag_suggestions import handle_tag_text, safe_assignment_confirm, install_tag_flow
from handlers.calendar_pdf import calendar_pdf_callback
import handlers.task as task_handler
import handlers.reports as reports_handler
import handlers.extra_reports as extra_reports_handler
from services import calendar_runtime
from services import calendar_runtime_extensions
from services import calendar_reports_v2
from services import calendar_report_legacy
from services.database import init_db


task_handler.format_task_card = calendar_runtime_extensions.format_task_card
task_handler.build_full_report = calendar_runtime_extensions.build_full_report
reports_handler.report_all_tasks = calendar_report_legacy.report_all_tasks
reports_handler.report_by_priority = calendar_report_legacy.report_by_priority
reports_handler.report_stuck = calendar_report_legacy.report_stuck
reports_handler.report_trend = calendar_report_legacy.report_trend
reports_handler.report_calendar = calendar_reports_v2.report_calendar
reports_handler.report_week = calendar_runtime.report_week
reports_handler.report_heatmap = calendar_reports_v2.report_heatmap
reports_handler.report_heatmap_week = calendar_runtime.report_heatmap_week
reports_handler.report_today = calendar_runtime.report_today
extra_reports_handler.report_compare_months = calendar_runtime.report_compare_months
report_compare_months = calendar_runtime.report_compare_months
deadline_selected = calendar_runtime_extensions.deadline_selected


async def handle_tag_callback(update, context):
    callback = getattr(task_handler, "_handle_tag_callback", None)
    if callback is None:
        await update.callback_query.answer("بخش تگ‌ها آماده نیست.", show_alert=True)
        return
    return await callback(update, context)


def _add_calendar_pdf_button(markup):
    rows = [list(row) for row in markup.inline_keyboard]
    if not any(button.callback_data == "report_calendar_pdf" for row in rows for button in row):
        rows.insert(-1, [InlineKeyboardButton("📄 خروجی PDF تقویم ماهانه", callback_data="report_calendar_pdf")])
    from telegram import InlineKeyboardMarkup
    return InlineKeyboardMarkup(rows)


reports_handler.reports_menu_keyboard = _add_calendar_pdf_button(reports_handler.reports_menu_keyboard()) if hasattr(reports_handler, "reports_menu_keyboard") else None
if reports_handler.reports_menu_keyboard is not None:
    _original_reports_menu_keyboard = reports_handler.reports_menu_keyboard
    def _reports_menu_keyboard_with_pdf():
        return _original_reports_menu_keyboard
    reports_handler.reports_menu_keyboard = _reports_menu_keyboard_with_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def bind_bot_context(update, context):
    profile = context.bot_data.get("bot_config")
    bot_key = profile.key if profile else "default"
    set_current_bot_key(bot_key)
    logger.debug("bot_context bound bot_key=%s user_id=%s", bot_key, getattr(update.effective_user, "id", None))
    calendar_runtime_extensions.set_current_user(update.effective_user.id if update.effective_user else None)


async def track_usage(update, context):
    user = update.effective_user
    if not user:
        return
    is_new = record_user(user, increment_usage=True)
    logger.info("user_activity user_id=%s username=%s full_name=%s chat_id=%s update_id=%s", user.id, user.username or "", user.full_name or "", update.effective_chat.id if update.effective_chat else "", update.update_id)
    if is_new:
        await notify_new_user(context, user)


def _parse_report_time():
    try:
        hour, minute = ADMIN_REPORT_TIME.split(":", 1)
        return dt_time(hour=int(hour), minute=int(minute))
    except Exception:
        logger.warning("Invalid ADMIN_REPORT_TIME=%s; falling back to 20:00", ADMIN_REPORT_TIME)
        return dt_time(hour=20, minute=0)


async def _jira_sync_job(context):
    profile = context.job.data if context.job and context.job.data else context.application.bot_data.get("bot_config")
    bot_key = profile.key if profile else "default"
    try:
        result = await run_jira_sync(bot_key)
        if result:
            changed, connections = result
            if changed:
                logger.info("Jira sync bot=%s changed=%s connections=%s", bot_key, changed, connections)
    except Exception:
        logger.exception("Jira sync failed for bot=%s", bot_key)


async def _integration_sync_job(context):
    profile = context.job.data if context.job.data else context.application.bot_data.get("bot_config")
    bot_key = profile.key if profile else "default"
    try:
        results = await run_external_sync(bot_key)
        if results:
            logger.info("External task sync bot=%s users=%s", bot_key, len(results))
    except Exception:
        logger.exception("External task sync failed for bot=%s", bot_key)


async def _oauth_callback(request):
    from aiohttp import web
    from services.integration_service import complete_oauth
    provider = request.match_info.get("provider")
    error = request.query.get("error")
    if error:
        return web.Response(text=f"اتصال لغو شد: {error}", content_type="text/html", charset="utf-8")
    code = request.query.get("code")
    state = request.query.get("state")
    if not code or not state:
        return web.Response(text="اطلاعات اتصال ناقص است.", status=400, content_type="text/html", charset="utf-8")
    try:
        complete_oauth(provider, code, state)
        return web.Response(text="<h2>اتصال با موفقیت انجام شد.</h2><p>می‌توانید به تلگرام برگردید و همگام‌سازی را اجرا کنید.</p>", content_type="text/html", charset="utf-8")
    except Exception as exc:
        logger.exception("OAuth callback failed")
        return web.Response(text=f"<h2>اتصال ناموفق بود.</h2><p>{str(exc)}</p>", status=500, content_type="text/html", charset="utf-8")


async def _start_oauth_server(app):
    base = os.getenv("INTEGRATION_REDIRECT_BASE_URL", "").strip()
    if not base:
        logger.info("External task OAuth server disabled: INTEGRATION_REDIRECT_BASE_URL is not set")
        return
    from aiohttp import web
    oauth_app = web.Application()
    oauth_app.router.add_get("/integrations/oauth/{provider}", _oauth_callback)
    runner = web.AppRunner(oauth_app)
    await runner.setup()
    host = os.getenv("INTEGRATION_HOST", "0.0.0.0")
    port = int(os.getenv("INTEGRATION_PORT", "8080"))
    site = web.TCPSite(runner, host, port)
    await site.start()
    app.bot_data["integration_oauth_runner"] = runner
    logger.info("External task OAuth callback listening on %s:%s", host, port)


async def post_init(app: Application):
    await init_db()
    profile = app.bot_data.get("bot_config")
    commands = [BotCommand("start", "شروع ربات و منوی اصلی"), BotCommand("add", "افزودن تسک جدید"), BotCommand("tasks", "منوی تسک‌ها"), BotCommand("unassigned", "وظایف بدون مسئول"), BotCommand("team", "تیم و فضای مشترک"), BotCommand("search", "جستجوی تسک"), BotCommand("templates", "تمپلیت‌های آماده"), BotCommand("reports", "گزارشات و آمار"), BotCommand("habit", "مدیریت عادت‌ها"), BotCommand("donate", "حمایت با Telegram Stars"), BotCommand("ai", "دستیار هوشمند تحلیل تسک‌ها"), BotCommand("jira", "اتصال به Jira"), BotCommand("jira_status", "وضعیت اتصال Jira"), BotCommand("jira_disconnect", "قطع اتصال Jira"), BotCommand("help", "راهنمای کامل استفاده")]
    feature_by_command = {"add": "tasks", "tasks": "tasks", "unassigned": "unassigned", "team": "teams", "search": "search", "templates": "templates", "reports": "reports", "habit": "habits", "donate": "donate", "ai": "ai"}
    if profile is not None:
        commands = [cmd for cmd in commands if profile.feature_enabled(feature_by_command.get(cmd.command, ""))]
    await app.bot.set_my_commands(commands)
    await _start_oauth_server(app)
    if app.job_queue:
        app.job_queue.run_repeating(morning_today_tasks, interval=60, first=10, name="morning_today_tasks")
        app.job_queue.run_repeating(midday_summary_and_weekly, interval=60, first=20, name="midday_summary_weekly")
        app.job_queue.run_repeating(habit_reminders, interval=60, first=10, name="habit_reminders")
        app.job_queue.run_repeating(weekly_habit_reports, interval=60, first=40, name="weekly_habit_reports")
        app.job_queue.run_daily(daily_admin_report, time=_parse_report_time(), name="daily_admin_report")
        bot_offset = sum(ord(ch) for ch in (profile.key if profile else "default")) % 60
        app.job_queue.run_repeating(_jira_sync_job, interval=60, first=30 + bot_offset, name="jira_sync", data=profile)
        app.job_queue.run_repeating(_integration_sync_job, interval=300, first=60 + bot_offset, name="external_task_sync", data=profile)
        logging.info("Jobs scheduled: tasks, habit reminders, weekly habit reports, throttled Jira/external sync.")
    else:
        logging.warning("JobQueue not available — reminders, Jira sync and external sync disabled.")


def _feature(app, name):
    profile = app.bot_data.get("bot_config")
    return profile is None or profile.feature_enabled(name)


def build_application(profile):
    request = HTTPXRequest(connection_pool_size=16, read_timeout=30.0, write_timeout=120.0, connect_timeout=30.0, pool_timeout=30.0, media_write_timeout=120.0, http_version="1.1")
    app = Application.builder().token(profile.token).request(request).post_init(post_init).build()
    app.bot_data["bot_config"] = profile
    install_tag_flow(task_handler)
    app.add_handler(TypeHandler(Update, bind_bot_context), group=-100)
    if _feature(app, "guest_mode"):
        app.add_handler(TypeHandler(Update, handle_guest_task), group=-2)
    app.add_handler(MessageHandler(filters.ALL, track_usage), group=-1)
    app.add_handler(TypeHandler(Update, handle_business_connection), group=-10)
    app.add_handler(TypeHandler(Update, handle_business_message), group=-10)
    app.add_handler(TypeHandler(Update, handle_edited_business_message), group=-10)
    app.add_handler(TypeHandler(Update, handle_deleted_business_messages), group=-10)
    app.add_handler(CommandHandler("start", start))
    if _feature(app, "tasks"):
        app.add_handler(CommandHandler("add", add_task))
        app.add_handler(CommandHandler("tasks", paginated_list_tasks))
    if _feature(app, "unassigned"):
        app.add_handler(CommandHandler("unassigned", unassigned_tasks))
    if _feature(app, "teams"):
        app.add_handler(CommandHandler("team", team_command))
    if _feature(app, "search"):
        app.add_handler(CommandHandler("search", search_command))
    if _feature(app, "templates"):
        app.add_handler(CommandHandler("templates", show_templates_menu))
    from handlers.help import help_command
    if _feature(app, "reports"):
        app.add_handler(CommandHandler("reports", show_reports_menu))
    if _feature(app, "habits"):
        app.add_handler(CommandHandler("habit", show_habit_menu))
    if _feature(app, "donate"):
        app.add_handler(CommandHandler("donate", donate_command))
    if _feature(app, "ai"):
        app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("jira_disconnect", jira_disconnect_command))
    app.add_handler(CommandHandler("jira_status", jira_status_command))
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("jira", jira_start)], states={JIRA_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, jira_type)], JIRA_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, jira_url)], JIRA_IDENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, jira_identity)], JIRA_CREDENTIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, jira_credential)], JIRA_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, jira_project)]}, fallbacks=[CommandHandler("cancel", jira_cancel)], name="jira_connection", persistent=False))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(start_task, pattern="^start_"))
    app.add_handler(CallbackQueryHandler(done_task, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(cancel_task, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(pending_task, pattern="^pending_"))
    app.add_handler(CallbackQueryHandler(take_confirm, pattern="^take_(confirm|cancel)$"))
    app.add_handler(CallbackQueryHandler(take_assignment, pattern="^take_[A-Za-z0-9]"))
    app.add_handler(CallbackQueryHandler(safe_assignment_confirm, pattern="^assign_confirm_create$"))
    app.add_handler(CallbackQueryHandler(assignment_callback, pattern="^assign_"))
    app.add_handler(CallbackQueryHandler(assignment_manage_callback, pattern="^(owner_|asg_|chg_)"))
    app.add_handler(CallbackQueryHandler(task_details_callback, pattern="^(task_details_|task_history_)") )
    app.add_handler(CallbackQueryHandler(comment_callback, pattern="^comment_add_"))
    app.add_handler(CallbackQueryHandler(comment_cancel_callback, pattern="^comment_cancel_"))
    app.add_handler(CallbackQueryHandler(paginated_detail_page, pattern="^detail_page_"))
    app.add_handler(CallbackQueryHandler(download_csv, pattern="^download_csv"))
    app.add_handler(CallbackQueryHandler(paginated_sort_callback, pattern="^sort_"))
    app.add_handler(CallbackQueryHandler(calendar_pdf_callback, pattern="^report_calendar_pdf$"))
    app.add_handler(CallbackQueryHandler(reports_callback, pattern="^report_"))
    app.add_handler(CallbackQueryHandler(report_compare_months, pattern="^report_compare$"))
    app.add_handler(CallbackQueryHandler(report_performance, pattern="^report_perf$"))
    app.add_handler(CallbackQueryHandler(report_progress_bar, pattern="^report_progress_bar$"))
    app.add_handler(CallbackQueryHandler(templates_callback, pattern="^tpl_"))
    app.add_handler(CallbackQueryHandler(priority_selected, pattern="^priority_"))
    app.add_handler(CallbackQueryHandler(deadline_selected, pattern="^deadline_"))
    # Tag callbacks must use a prefix match. The previous pattern ended with
    # '$', so only the literal values 'tag_'/'tags_' matched; real callbacks
    # such as tag_new/tag_pick_0/tag_none never reached handle_tag_callback.
    app.add_handler(CallbackQueryHandler(handle_tag_callback, pattern="^(tag_|tags_|step_back_description|step_back_category)"))
    app.add_handler(CallbackQueryHandler(optional_field_callback, pattern="^(category_pick_|category_skip|description_skip)"))
    app.add_handler(CallbackQueryHandler(share_category_callback, pattern="^share_cat_"))
    app.add_handler(CallbackQueryHandler(import_callback, pattern="^import_"))
    app.add_handler(CallbackQueryHandler(team_callback, pattern="^team_"))
    app.add_handler(CallbackQueryHandler(handle_habit_callback, pattern="^habit_"))
    app.add_handler(CallbackQueryHandler(custom_bot_callback, pattern="^custombot_"))
    app.add_handler(CallbackQueryHandler(donate_callback, pattern="^donate_(10|40|100)$"))
    app.add_handler(CallbackQueryHandler(integration_callback, pattern="^int_"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!priority_|deadline_|category_pick_|category_skip|tag_|tags_|step_back_description|step_back_category|description_skip|detail_page_|download_csv|start_|done_|cancel_|pending_|take_|assign_|owner_|asg_|chg_|task_details_|task_history_|comment_add_|comment_cancel_|report_|tpl_|sort_|share_cat_|import_|team_|habit_|donate_|custombot_|int_)"))
    comment_message_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
        | filters.ANIMATION
        | filters.Sticker.ALL
        | filters.CONTACT
        | filters.LOCATION
    ) & ~filters.COMMAND
    app.add_handler(MessageHandler(comment_message_filter, handle_tag_text), group=0)
    app.add_error_handler(error_handler)
    return app


def main():
    apps = [build_application(profile) for profile in BOT_PROFILES]
    logger.info("Starting %s bot application(s): %s", len(apps), ", ".join(p.key for p in BOT_PROFILES))
    if len(apps) == 1:
        apps[0].run_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])
    else:
        asyncio.run(run_applications(apps))


if __name__ == "__main__":
    main()
