import asyncio
import logging
from datetime import time as dt_time

from telegram import BotCommand, BotCommandScopeChat, InlineKeyboardButton, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    TypeHandler,
    filters,
)
from telegram.request import HTTPXRequest

import handlers.extra_reports as extra_reports_handler
import handlers.reports as reports_handler
import handlers.task as task_handler
from bot_context import set_current_bot_key, set_current_user_id
from config import ADMIN_REPORT_TIME, BOT_PROFILES
from handlers.ai import ai_command
from handlers.business import (
    handle_business_connection,
    handle_business_message,
    handle_deleted_business_messages,
    handle_edited_business_message,
)
from handlers.calendar_pdf import calendar_pdf_callback
from handlers.custom_bot import custom_bot_callback
from handlers.donate import (
    donate_callback,
    donate_command,
    precheckout_callback,
    successful_payment_callback,
)
from handlers.extra_reports import report_performance, report_progress_bar
from handlers.guest import handle_guest_task
from handlers.habits import handle_habit_callback, show_habit_menu
from handlers.import_bulk import import_callback
from handlers.integrations import integration_callback
from handlers.jira import (
    JIRA_CREDENTIAL,
    JIRA_IDENTITY,
    JIRA_PROJECT,
    JIRA_TYPE,
    JIRA_URL,
    jira_cancel,
    jira_credential,
    jira_disconnect_command,
    jira_identity,
    jira_project,
    jira_start,
    jira_status_command,
    jira_type,
    jira_url,
)
from handlers.menu import button_handler
from handlers.backoffice import backoffice_command
from handlers.reports import reports_callback, show_reports_menu
from handlers.search_share import search_command, share_category_callback
from handlers.start import start
from handlers.tag_suggestions import (
    handle_tag_text,
    install_tag_flow,
    safe_assignment_confirm,
)
from handlers.task import (
    add_task,
    assignment_callback,
    assignment_manage_callback,
    cancel_task,
    comment_callback,
    comment_cancel_callback,
    detail_page,
    done_task,
    download_csv,
    list_tasks,
    optional_field_callback,
    pending_task,
    priority_selected,
    save_task,
    sort_tasks_callback,
    start_task,
    take_assignment,
    take_confirm,
    task_details_callback,
    unassigned_tasks,
)
from handlers.task_pagination import (
    paginated_detail_page,
    paginated_list_tasks,
    paginated_sort_callback,
    tasks_view_callback,
)
from handlers.team import team_callback, team_command
from handlers.templates import show_templates_menu, templates_callback
from handlers.voice import handle_voice_message
from logging_config import setup_logging
from services import (
    calendar_report_legacy,
    calendar_reports_v2,
    calendar_runtime,
    calendar_runtime_extensions,
)
from services.admin_service import daily_admin_report, error_handler, notify_new_user
from services.bot_runtime_manager import run_runtime_control_plane
from services.database import init_db
from services.database_backup import (
    BACKUP_FIRST_RUN_SECONDS,
    BACKUP_INTERVAL_SECONDS,
    database_backup_job,
)
from services.integration_oauth_runtime import (
    start_integration_oauth_server,
    stop_integration_oauth_server,
)
from services.reminders import (
    habit_reminders,
    midday_summary_and_weekly,
    morning_today_tasks,
    weekly_habit_reports,
)
from services.sync_scheduler import run_external_sync, run_jira_sync
from services.task_capabilities import install_task_capabilities, task_option_enabled
from services.user_service import record_user_async

setup_logging()
task_handler.format_task_card=calendar_runtime_extensions.format_task_card
task_handler.build_full_report=calendar_runtime_extensions.build_full_report
reports_handler.report_all_tasks=calendar_report_legacy.report_all_tasks
reports_handler.report_by_priority=calendar_report_legacy.report_by_priority
reports_handler.report_stuck=calendar_report_legacy.report_stuck
reports_handler.report_trend=calendar_report_legacy.report_trend
reports_handler.report_calendar=calendar_reports_v2.report_calendar
reports_handler.report_week=calendar_runtime.report_week
reports_handler.report_heatmap=calendar_reports_v2.report_heatmap
reports_handler.report_heatmap_week=calendar_runtime.report_heatmap_week
reports_handler.report_today=calendar_runtime.report_today
extra_reports_handler.report_compare_months=calendar_runtime.report_compare_months
report_compare_months=calendar_runtime.report_compare_months

async def handle_tag_callback(update,context):
    callback=getattr(task_handler,"_handle_tag_callback",None)
    if callback is None:
        await update.callback_query.answer("بخش تگ‌ها آماده نیست.",show_alert=True);return
    return await callback(update,context)

_TAG_CALLBACK_EXCLUSION_MARKER="|tag_|tags_|step_back_description|step_back_category|"
_PRIORITY_CALLBACK_MARKER="priority_high priority_medium"
_CAPABILITY_OPTION_CONTRACT={"search": "allow_search", "templates": "allow_templates", "bulk_import": "allow_bulk_import"}

def _add_calendar_pdf_button(markup):
    rows=[list(row) for row in markup.inline_keyboard]
    if not any(button.callback_data=="report_calendar_pdf" for row in rows for button in row):rows.insert(-1,[InlineKeyboardButton("📄 خروجی PDF تقویم ماهانه",callback_data="report_calendar_pdf")])
    from telegram import InlineKeyboardMarkup
    return InlineKeyboardMarkup(rows)

if hasattr(reports_handler,"reports_menu_keyboard"):
    _original_reports_menu_keyboard=reports_handler.reports_menu_keyboard
    def _reports_menu_keyboard_with_pdf_and_web():
        from webapp.report_routes import add_monthly_web_button
        return add_monthly_web_button(_add_calendar_pdf_button(_original_reports_menu_keyboard()))
    reports_handler.reports_menu_keyboard=_reports_menu_keyboard_with_pdf_and_web
logger=logging.getLogger(__name__)

async def bind_bot_context(update,context):
    profile=context.bot_data.get("bot_config");bot_key=profile.key if profile else "default";set_current_bot_key(bot_key);set_current_user_id(update.effective_user.id if update.effective_user else "");logger.debug("bot_context bound bot_key=%s user_id=%s",bot_key,getattr(update.effective_user,"id",None));calendar_runtime_extensions.set_current_user(update.effective_user.id if update.effective_user else None)
async def track_usage(update,context):
    user=update.effective_user
    if not user:return
    is_new=await record_user_async(user,increment_usage=True);logger.info("user_activity user_id=%s username=%s full_name=%s chat_id=%s update_id=%s",user.id,user.username or "",user.full_name or "",update.effective_chat.id if update.effective_chat else "",update.update_id)
    if is_new:await notify_new_user(context,user)
def _parse_report_time():
    try:
        hour,minute=ADMIN_REPORT_TIME.split(":",1);return dt_time(hour=int(hour),minute=int(minute))
    except Exception:logger.warning("Invalid ADMIN_REPORT_TIME=%s; falling back to 20:00",ADMIN_REPORT_TIME);return dt_time(hour=20,minute=0)
async def _jira_sync_job(context):
    profile=context.job.data if context.job and context.job.data else context.application.bot_data.get("bot_config");await run_jira_sync(bot_key=profile.key if profile else "default")
async def _integration_sync_job(context):
    profile=context.job.data if context.job and context.job.data else context.application.bot_data.get("bot_config")
    providers=("microsoft","google") if profile is None or profile.feature_enabled("google_tasks") else ("microsoft",)
    await run_external_sync(bot_key=profile.key if profile else "default",providers=providers)

def _job_registered(job_queue,name):
    getter=getattr(job_queue,"get_jobs_by_name",None)
    return bool(getter(name)) if getter is not None else False

def _run_repeating_once(job_queue,callback,*,name,**kwargs):
    if _job_registered(job_queue,name):return
    job_queue.run_repeating(callback,name=name,**kwargs)

def _run_daily_once(job_queue,callback,*,name,**kwargs):
    if _job_registered(job_queue,name):return
    job_queue.run_daily(callback,name=name,**kwargs)

_database_backup_registered = False

async def post_init(app:Application):
    await init_db();install_task_capabilities(app);profile=app.bot_data.get("bot_config")
    commands=[BotCommand("ai","دستیار هوشمند تحلیل تسک‌ها"),BotCommand("clinic","فضای کار کلینیک"),BotCommand("start","شروع ربات و منوی اصلی"),BotCommand("add","افزودن تسک جدید"),BotCommand("reports","گزارشات و آمار"),BotCommand("tasks","منوی تسک‌ها"),BotCommand("unassigned","وظایف بدون مسئول"),BotCommand("team","تیم و فضای مشترک"),BotCommand("search","جستجوی تسک"),BotCommand("templates","تمپلیت‌های آماده"),BotCommand("habit","مدیریت عادت‌ها"),BotCommand("donate","حمایت با Telegram Stars"),BotCommand("jira","اتصال به Jira"),BotCommand("jira_status","وضعیت اتصال Jira"),BotCommand("jira_disconnect","قطع اتصال Jira"),BotCommand("help","راهنمای کامل استفاده")]
    feature_by_command={"clinic":"healthcare","add":"tasks","tasks":"tasks","unassigned":"unassigned","team":"teams","search":"search","templates":"templates","reports":"reports","habit":"habits","donate":"donate","ai":"ai","jira":"jira","jira_status":"jira","jira_disconnect":"jira"}
    permission_by_command={"add":"tasks.create","tasks":"tasks.view","unassigned":"unassigned.view","team":"teams.view","search":"search.use","templates":"templates.use","reports":"reports.view","habit":"habits.manage","donate":"donate.use","ai":"ai.use","jira":"integrations.manage","jira_status":"integrations.manage","jira_disconnect":"integrations.manage"}
    if profile is not None:
        filtered=[]
        for cmd in commands:
            feature=feature_by_command.get(cmd.command)
            permission=permission_by_command.get(cmd.command)
            if cmd.command=="start" or (feature and profile.feature_enabled(feature) and (not permission or profile.permission_enabled(permission))):
                if cmd.command=="search" and not task_option_enabled(app,"allow_search"):continue
                if cmd.command=="templates" and not task_option_enabled(app,"allow_templates"):continue
                filtered.append(cmd)
        commands=filtered
    await app.bot.delete_my_commands();await app.bot.set_my_commands(commands);logger.info("Telegram command menu updated bot=%s features=%s commands=%s",profile.key if profile else "default",profile.features if profile else {},", ".join(f"/{cmd.command}" for cmd in commands))
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        if profile is not None and profile.key != "default":
            break
        if str(admin_id).strip().isdigit():
            try:
                await app.bot.set_my_commands(commands + [BotCommand("backoffice", "لینک موقت پنل مدیریت")], scope=BotCommandScopeChat(int(admin_id)))
            except BadRequest as exc:
                # A user who has not opened this bot yet is not a resolvable
                # chat for Telegram. Do not prevent a managed bot from
                # starting just because its admin menu cannot be registered.
                logger.warning("Admin command menu unavailable bot=%s admin=%s: %s", profile.key if profile else "default", admin_id, exc)
    if app.job_queue:
        if profile is not None and profile.feature_enabled("healthcare") and profile.feature_enabled("clinic_staff_reminders"):
            from services.healthcare.notifications import staff_notification_job
            _run_repeating_once(app.job_queue,staff_notification_job,interval=60,first=15,name="clinic_staff_notifications")
        if profile is None or (profile.feature_enabled("reminders") and profile.permission_enabled("reminders.run")):
            _run_repeating_once(app.job_queue,morning_today_tasks,interval=60,first=10,name="morning_today_tasks")
            _run_repeating_once(app.job_queue,midday_summary_and_weekly,interval=60,first=20,name="midday_summary_weekly")
        if profile is None or (profile.feature_enabled("habits") and profile.permission_enabled("habits.manage")):
            _run_repeating_once(app.job_queue,habit_reminders,interval=60,first=10,name="habit_reminders")
            _run_repeating_once(app.job_queue,weekly_habit_reports,interval=60,first=40,name="weekly_habit_reports")
        if profile is None or profile.permission_enabled("reports.view"):
            _run_daily_once(app.job_queue,daily_admin_report,time=_parse_report_time(),name="daily_admin_report")
        global _database_backup_registered
        # A process can host several managed bots, but the database is shared.
        # Register one daily backup job only; otherwise every bot sends the
        # same archive to the admins from its own job queue.
        if not _database_backup_registered:
            _run_repeating_once(app.job_queue, database_backup_job, interval=BACKUP_INTERVAL_SECONDS, first=BACKUP_FIRST_RUN_SECONDS, name="database_backup")
            _database_backup_registered = True
        if profile is None or (profile.feature_enabled("integrations") and profile.permission_enabled("integrations.sync")):
            bot_offset=sum(ord(ch) for ch in (profile.key if profile else "default"))%60
            if profile is None or profile.feature_enabled("jira"):
                _run_repeating_once(app.job_queue,_jira_sync_job,interval=60,first=30+bot_offset,name="jira_sync",data=profile)
            _run_repeating_once(app.job_queue,_integration_sync_job,interval=300,first=60+bot_offset,name="external_task_sync",data=profile)

def _feature(app,name):
    profile=app.bot_data.get("bot_config")
    if profile is None or not profile.feature_enabled(name):return False
    option={"search":"allow_search","templates":"allow_templates","bulk_import":"allow_bulk_import"}.get(name);return option is None or task_option_enabled(app,option)
def _permission(app,name):
    profile=app.bot_data.get("bot_config")
    return profile is None or profile.permission_enabled(name)
_CAPABILITY_FEATURE_CONTRACT={"search": "allow_search", "templates": "allow_templates", "bulk_import": "allow_bulk_import"}
def build_application(profile):
    request=HTTPXRequest(connection_pool_size=16,read_timeout=30.0,write_timeout=120.0,connect_timeout=30.0,pool_timeout=30.0,media_write_timeout=120.0,http_version="1.1");app=Application.builder().token(profile.token).request(request).post_init(post_init).build();app.bot_data["bot_config"]=profile
    if not getattr(task_handler,"_tag_flow_installed",False):install_tag_flow(task_handler)
    app.add_handler(TypeHandler(Update,bind_bot_context),group=-100)
    if _feature(app,"guest_mode") and _permission(app,"guest_mode.use"):app.add_handler(TypeHandler(Update,handle_guest_task),group=-2)
    app.add_handler(MessageHandler(filters.ALL,track_usage),group=-1);app.add_handler(TypeHandler(Update,handle_business_connection),group=-10);app.add_handler(TypeHandler(Update,handle_business_message),group=-10);app.add_handler(TypeHandler(Update,handle_edited_business_message),group=-10);app.add_handler(TypeHandler(Update,handle_deleted_business_messages),group=-10);app.add_handler(CommandHandler("start", start));
    if profile.key == "default":
        app.add_handler(CommandHandler("backoffice", backoffice_command))
    if _feature(app,"tasks") and _permission(app,"tasks.create"):app.add_handler(CommandHandler("add", add_task))
    if _feature(app,"tasks") and _permission(app,"tasks.view"):app.add_handler(CommandHandler("tasks",paginated_list_tasks))
    if _feature(app,"unassigned") and _permission(app,"unassigned.view"):app.add_handler(CommandHandler("unassigned",unassigned_tasks))
    if _feature(app,"teams") and _permission(app,"teams.view"):app.add_handler(CommandHandler("team",team_command))
    if _feature(app,"healthcare"):
        from handlers.clinic import clinic_callback, clinic_menu, handle_clinic_input
        app.add_handler(CommandHandler("clinic",clinic_menu))
        app.add_handler(CallbackQueryHandler(clinic_callback,pattern="^clinic:"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_clinic_input), group=0)
    if _feature(app,"search") and _permission(app,"search.use"):app.add_handler(CommandHandler("search",search_command))
    if _feature(app,"templates") and _permission(app,"templates.use"):app.add_handler(CommandHandler("templates",show_templates_menu))
    from handlers.help import help_command
    if _feature(app,"reports") and _permission(app,"reports.view"):app.add_handler(CommandHandler("reports",show_reports_menu))
    if _feature(app,"habits") and _permission(app,"habits.manage"):app.add_handler(CommandHandler("habit",show_habit_menu))
    if _feature(app,"donate") and _permission(app,"donate.use"):app.add_handler(CommandHandler("donate",donate_command))
    if _feature(app,"ai") and _permission(app,"ai.use"):app.add_handler(CommandHandler("ai",ai_command))
    if _feature(app,"jira") and _permission(app,"integrations.manage"):
        app.add_handler(ConversationHandler(entry_points=[CommandHandler("jira",jira_start)],states={JIRA_TYPE:[MessageHandler(filters.TEXT & ~filters.COMMAND,jira_type)],JIRA_URL:[MessageHandler(filters.TEXT & ~filters.COMMAND,jira_url)],JIRA_IDENTITY:[MessageHandler(filters.TEXT & ~filters.COMMAND,jira_identity)],JIRA_CREDENTIAL:[MessageHandler(filters.TEXT & ~filters.COMMAND,jira_credential)],JIRA_PROJECT:[MessageHandler(filters.TEXT & ~filters.COMMAND,jira_project)]},fallbacks=[CommandHandler("cancel",jira_cancel)],name="jira_connection",persistent=False));app.add_handler(CommandHandler("jira_disconnect",jira_disconnect_command));app.add_handler(CommandHandler("jira_status",jira_status_command))
    app.add_handler(CommandHandler("help",help_command))
    if _feature(app,"tasks"):
        if _permission(app,"tasks.status"):
            app.add_handler(CallbackQueryHandler(start_task,pattern="^start_"))
            app.add_handler(CallbackQueryHandler(done_task,pattern="^done_"))
            app.add_handler(CallbackQueryHandler(cancel_task,pattern="^cancel_"))
            app.add_handler(CallbackQueryHandler(pending_task,pattern="^pending_"))
        if _permission(app,"tasks.view"):
            app.add_handler(CallbackQueryHandler(task_details_callback,pattern="^(task_details_|task_history_)"))
            app.add_handler(CallbackQueryHandler(paginated_detail_page,pattern="^detail_page_"))
            app.add_handler(CallbackQueryHandler(paginated_sort_callback,pattern="^sort_page_"))
            app.add_handler(CallbackQueryHandler(sort_tasks_callback,pattern="^sort_"))
            app.add_handler(CallbackQueryHandler(tasks_view_callback,pattern="^(?:view_tasks_|tasks_filter_)"))
        if _feature(app,"priority") and _permission(app,"priority.set"):
            app.add_handler(CallbackQueryHandler(priority_selected,pattern="^priority_(high|medium|low)$"))
        if _feature(app,"deadline") and _permission(app,"deadline.set"):
            app.add_handler(CallbackQueryHandler(deadline_selected,pattern="^deadline_(?:0|1|2|3|4|5|6|7|custom|none)$"))
        if _permission(app,"tasks.create"):
            app.add_handler(CallbackQueryHandler(optional_field_callback,pattern="^(?:category_skip|category_pick_[0-9]+|tags_skip|description_skip)$"))
        if _feature(app,"tags") and _permission(app,"tags.manage"):
            app.add_handler(CallbackQueryHandler(handle_tag_callback,pattern="^(tag_|tags_|step_back_description|step_back_category)"))
        # Confirmation and cancellation are part of task creation, not
        # assignment. They must remain available for assignment-disabled bots.
        if _permission(app,"tasks.create"):
            app.add_handler(CallbackQueryHandler(safe_assignment_confirm,pattern="^assign_confirm_create$"))
            app.add_handler(CallbackQueryHandler(assignment_callback,pattern="^assign_cancel_create$"))
        if _feature(app,"assignment") and _permission(app,"assignment.manage"):
            app.add_handler(CallbackQueryHandler(take_confirm,pattern="^take_(confirm|cancel)$"))
            app.add_handler(CallbackQueryHandler(take_assignment,pattern="^take_[A-Za-z0-9]"))
            app.add_handler(CallbackQueryHandler(assignment_callback,pattern="^assign_"))
            app.add_handler(CallbackQueryHandler(assignment_manage_callback,pattern="^(owner_|asg_|chg_)"))
        if _feature(app,"comments") and _permission(app,"comments.manage"):
            app.add_handler(CallbackQueryHandler(comment_callback,pattern="^comment_add_"))
            app.add_handler(CallbackQueryHandler(comment_cancel_callback,pattern="^comment_cancel_"))
        if _feature(app,"categories") and _permission(app,"categories.manage"):
            app.add_handler(CallbackQueryHandler(share_category_callback,pattern="^share_"))
        if _feature(app,"bulk_import") and _permission(app,"bulk_import.use"):
            app.add_handler(CallbackQueryHandler(import_callback,pattern="^import_"))
        if _permission(app,"tasks.create"):
            app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.LOCATION, save_task))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_tag_text))
    if _feature(app,"integrations") and _permission(app,"integrations.manage"):
        app.add_handler(CallbackQueryHandler(integration_callback,pattern="^int_"))
    if _feature(app,"reports") and _permission(app,"reports.view"):
        app.add_handler(CallbackQueryHandler(reports_callback,pattern="^report_"))
        app.add_handler(CallbackQueryHandler(calendar_pdf_callback,pattern="^report_calendar_pdf$"))
    if _feature(app,"templates") and _permission(app,"templates.use"):
        app.add_handler(CallbackQueryHandler(templates_callback,pattern="^template_"))
    if _feature(app,"teams") and _permission(app,"teams.manage"):
        app.add_handler(CallbackQueryHandler(team_callback,pattern="^team_"))
    if _feature(app,"habits") and _permission(app,"habits.manage"):
        app.add_handler(CallbackQueryHandler(handle_habit_callback,pattern="^habit_"))
    if _feature(app,"donate") and _permission(app,"donate.use"):
        app.add_handler(CallbackQueryHandler(donate_callback,pattern="^donate_"))
        app.add_handler(CallbackQueryHandler(precheckout_callback,pattern="^precheckout_"))
        app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment_callback))
    async def support_callback(update, context):
        await update.callback_query.answer()
        context.user_data["step"] = "support_ticket"
        await update.callback_query.message.reply_text("✉️ پیام خود را برای پشتیبانی ارسال کنید. پس از ارسال، شماره تیکت دریافت می‌کنید.")
    app.add_handler(CallbackQueryHandler(support_callback,pattern="^contact_new$"))
    app.add_handler(CallbackQueryHandler(button_handler,pattern="^(?:add_task(?:_manual)?|ai_menu|ai_start|ai_(?:task|habit)_.+|tasks(?:_list|_back)?|search|teams|templates|habit_menu|stats|help|settings(?:_(?:timezone|date_format|language))?|timezone_set_.+|date_format_(?:jalali|gregorian)|language_(?:fa|en)|integrations|custom_bot|import_bulk|download_csv|contact_us)$"))
    if _feature(app,"voice") and _permission(app,"voice.use"):
        app.add_handler(MessageHandler(filters.VOICE,handle_voice_message))
    app.add_error_handler(error_handler);return app
def main():
    logger.info(
        "Starting dynamic bot runtime with %s initial profile(s): %s",
        len(BOT_PROFILES),
        ", ".join(p.key for p in BOT_PROFILES),
    )
    asyncio.run(
        run_runtime_control_plane(
            build_application,
            initial_profiles=BOT_PROFILES,
            startup_hook=start_integration_oauth_server,
            shutdown_hook=stop_integration_oauth_server,
        )
    )
if __name__=="__main__":main()
