import logging
from datetime import time as dt_time

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    TypeHandler,
    filters
)

from config import BOT_TOKEN, ADMIN_REPORT_TIME

from handlers.start import start
from handlers.menu import button_handler

from handlers.task import (
    add_task,
    save_task,
    list_tasks,
    priority_selected,
    deadline_selected,
    optional_field_callback,
    detail_page,
    download_csv,
    start_task,
    done_task,
    cancel_task,
    pending_task,
    sort_tasks_callback,
    assignment_callback,
    unassigned_tasks,
    take_assignment,
    take_confirm,
    assignment_manage_callback,
)

from handlers.reports import (
    show_reports_menu,
    reports_callback
)

from handlers.templates import (
    show_templates_menu,
    templates_callback
)

from handlers.search_share import search_command, share_category_callback
from handlers.extra_reports import report_compare_months, report_performance, report_progress_bar
from handlers.import_bulk import import_callback
from handlers.team import team_command, team_callback
from services.reminders import morning_today_tasks, midday_summary_and_weekly, habit_reminders, weekly_habit_reports
from services.csv_manager import init_csv
from services.team_manager import init_teams
from services.habit_service import init_habits
from services.user_service import init_users, record_user
from services.admin_service import notify_new_user, daily_admin_report, error_handler
from handlers.habits import handle_habit_callback, show_habit_menu
from handlers.donate import donate_callback, donate_command, precheckout_callback, successful_payment_callback
from handlers.guest import handle_guest_task
from handlers.ai import ai_command


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def track_usage(update, context):
    user = update.effective_user
    if not user:
        return
    is_new = record_user(user, increment_usage=True)
    logger.info(
        "user_activity user_id=%s username=%s full_name=%s chat_id=%s update_id=%s",
        user.id,
        user.username or "",
        user.full_name or "",
        update.effective_chat.id if update.effective_chat else "",
        update.update_id,
    )
    if is_new:
        await notify_new_user(context, user)


def _parse_report_time():
    try:
        hour, minute = ADMIN_REPORT_TIME.split(":", 1)
        return dt_time(hour=int(hour), minute=int(minute))
    except Exception:
        logger.warning("Invalid ADMIN_REPORT_TIME=%s; falling back to 20:00", ADMIN_REPORT_TIME)
        return dt_time(hour=20, minute=0)


async def post_init(app: Application):
    commands = [
        BotCommand("start", "شروع ربات و منوی اصلی"),
        BotCommand("add", "افزودن تسک جدید"),
        BotCommand("tasks", "منوی تسک‌ها"),
        BotCommand("unassigned", "وظایف بدون مسئول"),
        BotCommand("team", "تیم و فضای مشترک"),
        BotCommand("search", "جستجوی تسک"),
        BotCommand("templates", "تمپلیت‌های آماده"),
        BotCommand("reports", "گزارشات و آمار"),
        BotCommand("habit", "مدیریت عادت‌ها"),
        BotCommand("donate", "حمایت با Telegram Stars"),
        BotCommand("ai", "دستیار هوشمند تحلیل تسک‌ها"),
        BotCommand("help", "راهنمای کامل استفاده"),
    ]
    await app.bot.set_my_commands(commands)

    if app.job_queue:
        app.job_queue.run_repeating(
            morning_today_tasks,
            interval=60,
            first=10,
            name="morning_today_tasks",
        )
        app.job_queue.run_repeating(
            midday_summary_and_weekly,
            interval=60,
            first=20,
            name="midday_summary_weekly",
        )
        app.job_queue.run_repeating(
            habit_reminders,
            interval=60,
            first=10,
            name="habit_reminders",
        )
        app.job_queue.run_repeating(
            weekly_habit_reports,
            interval=60,
            first=40,
            name="weekly_habit_reports",
        )
        app.job_queue.run_daily(
            daily_admin_report,
            time=_parse_report_time(),
            name="daily_admin_report",
        )
        logging.info("Jobs scheduled: tasks, habit reminders, weekly habit reports.")
    else:
        logging.warning("JobQueue not available — reminders disabled.")

    logging.info("Bot commands registered.")


def main():
    init_csv()
    init_teams()
    init_habits()
    init_users()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(TypeHandler(Update, handle_guest_task), group=-2)
    app.add_handler(MessageHandler(filters.ALL, track_usage), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("unassigned", unassigned_tasks))
    app.add_handler(CommandHandler("team", team_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("templates", show_templates_menu))
    from handlers.help import help_command
    app.add_handler(CommandHandler("reports", show_reports_menu))
    app.add_handler(CommandHandler("habit", show_habit_menu))
    app.add_handler(CommandHandler("donate", donate_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CallbackQueryHandler(start_task, pattern="^start_"))
    app.add_handler(CallbackQueryHandler(done_task, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(cancel_task, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(pending_task, pattern="^pending_"))
    app.add_handler(CallbackQueryHandler(take_confirm, pattern="^take_(confirm|cancel)$"))
    app.add_handler(CallbackQueryHandler(take_assignment, pattern="^take_[A-Za-z0-9]"))
    app.add_handler(CallbackQueryHandler(assignment_callback, pattern="^assign_"))
    app.add_handler(CallbackQueryHandler(assignment_manage_callback, pattern="^(owner_|asg_|chg_)"))

    app.add_handler(CallbackQueryHandler(detail_page, pattern="^detail_page_"))
    app.add_handler(CallbackQueryHandler(download_csv, pattern="^download_csv"))
    app.add_handler(CallbackQueryHandler(sort_tasks_callback, pattern="^sort_"))

    app.add_handler(CallbackQueryHandler(reports_callback, pattern="^report_"))
    app.add_handler(CallbackQueryHandler(report_compare_months, pattern="^report_compare$"))
    app.add_handler(CallbackQueryHandler(report_performance, pattern="^report_perf$"))
    app.add_handler(CallbackQueryHandler(report_progress_bar, pattern="^report_progress_bar$"))

    app.add_handler(CallbackQueryHandler(templates_callback, pattern="^tpl_"))
    app.add_handler(CallbackQueryHandler(priority_selected, pattern="^priority_"))
    app.add_handler(CallbackQueryHandler(deadline_selected, pattern="^deadline_"))
    app.add_handler(CallbackQueryHandler(optional_field_callback, pattern="^(category_pick_|category_skip|tags_skip|description_skip)"))

    app.add_handler(CallbackQueryHandler(share_category_callback, pattern="^share_cat_"))
    app.add_handler(CallbackQueryHandler(import_callback, pattern="^import_"))
    app.add_handler(CallbackQueryHandler(team_callback, pattern="^team_"))
    app.add_handler(CallbackQueryHandler(handle_habit_callback, pattern="^habit_"))
    app.add_handler(CallbackQueryHandler(donate_callback, pattern="^donate_(10|40|100)$"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=(
                "^(?!priority_|deadline_|category_pick_|category_skip|tags_skip|description_skip|"
                "detail_page_|download_csv|start_|done_|cancel_|pending_|take_|assign_|owner_|"
                "asg_|chg_|report_|tpl_|sort_|share_cat_|import_|team_|habit_|donate_)"
            )
        )
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)
    )

    app.add_error_handler(error_handler)

    logger.info("Task Bot Started...")
    app.run_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])


if __name__ == "__main__":
    main()
