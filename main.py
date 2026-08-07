import logging
from datetime import time as dt_time

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from config import BOT_TOKEN

from handlers.start import start
from handlers.menu import button_handler

from handlers.task import (
    add_task,
    save_task,
    list_tasks,
    priority_selected,
    deadline_selected,
    skip_field,
    detail_page,
    download_csv,
    start_task,
    done_task,
    cancel_task,
    pending_task,
    sort_tasks_callback,
)

from handlers.reports import (
    show_reports_menu,
    reports_callback
)

from handlers.templates import (
    show_templates_menu,
    templates_callback
)

from handlers.search_share import search_command, share_command, share_category_callback
from handlers.extra_reports import report_compare_months, report_performance, report_progress_bar
from handlers.import_bulk import import_callback
from handlers.team import team_command, team_callback
from services.reminders import morning_today_tasks, midday_summary_and_weekly, habit_reminders, weekly_habit_reports
from services.csv_manager import init_csv
from services.team_manager import init_teams
from services.habit_service import init_habits
from handlers.habits import handle_habit_callback


logging.basicConfig(level=logging.INFO)


async def post_init(app: Application):
    commands = [
        BotCommand("start", "شروع ربات و منوی اصلی"),
        BotCommand("add", "افزودن تسک جدید"),
        BotCommand("tasks", "منوی تسک‌ها"),
        BotCommand("team", "تیم و فضای مشترک"),
        BotCommand("search", "جستجوی تسک"),
        BotCommand("share", "اشتراک‌گذاری لیست / دسته"),
        BotCommand("templates", "تمپلیت‌های آماده"),
        BotCommand("reports", "گزارشات و آمار"),
        BotCommand("skip", "رد کردن فیلد اختیاری"),
    ]
    await app.bot.set_my_commands(commands)

    if app.job_queue:
        app.job_queue.run_daily(
            morning_today_tasks,
            time=dt_time(hour=7, minute=0),
            name="morning_today_tasks",
        )
        app.job_queue.run_daily(
            midday_summary_and_weekly,
            time=dt_time(hour=11, minute=0),
            name="midday_summary_weekly",
        )
        app.job_queue.run_repeating(
            habit_reminders,
            interval=60,
            first=10,
            name="habit_reminders",
        )
        app.job_queue.run_daily(
            weekly_habit_reports,
            time=dt_time(hour=18, minute=0),
            days=(4,),
            name="weekly_habit_reports",
        )
        logging.info("Jobs scheduled: tasks, habit reminders, weekly habit reports.")
    else:
        logging.warning("JobQueue not available — reminders disabled.")

    logging.info("Bot commands registered.")


def main():
    init_csv()
    init_teams()
    init_habits()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("team", team_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("share", share_command))
    app.add_handler(CommandHandler("templates", show_templates_menu))
    app.add_handler(CommandHandler("reports", show_reports_menu))
    app.add_handler(CommandHandler("skip", skip_field))

    app.add_handler(CallbackQueryHandler(start_task, pattern="^start_"))
    app.add_handler(CallbackQueryHandler(done_task, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(cancel_task, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(pending_task, pattern="^pending_"))

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

    app.add_handler(CallbackQueryHandler(share_category_callback, pattern="^share_cat_"))
    app.add_handler(CallbackQueryHandler(import_callback, pattern="^import_"))
    app.add_handler(CallbackQueryHandler(team_callback, pattern="^team_"))
    app.add_handler(CallbackQueryHandler(handle_habit_callback, pattern="^habit_"))

    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=(
                "^(?!priority_|deadline_|detail_page_|download_csv|"
                "start_|done_|cancel_|pending_|report_|tpl_|sort_|"
                "share_cat_|import_|team_|habit_)"
            )
        )
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, save_task)
    )

    logging.info("Task Bot Started...")
    app.run_polling()


if __name__ == "__main__":
    main()
