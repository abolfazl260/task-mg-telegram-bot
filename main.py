import logging

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
    pending_task
)

from handlers.reports import (
    show_reports_menu,
    reports_callback
)

from handlers.templates import (
    show_templates_menu,
    templates_callback
)

from services.csv_manager import init_csv


logging.basicConfig(
    level=logging.INFO
)


async def post_init(app: Application):
    """Register bot commands so Telegram suggests them automatically."""

    commands = [
        BotCommand("start", "شروع ربات و منوی اصلی"),
        BotCommand("add", "افزودن تسک جدید"),
        BotCommand("tasks", "مشاهده تسک‌های فعال"),
        BotCommand("templates", "تمپلیت‌های آماده"),
        BotCommand("reports", "گزارشات و آمار"),
        BotCommand("skip", "رد کردن فیلد اختیاری"),
    ]

    await app.bot.set_my_commands(commands)
    logging.info("Bot commands registered.")


def main():

    init_csv()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("templates", show_templates_menu))
    app.add_handler(CommandHandler("reports", show_reports_menu))
    app.add_handler(CommandHandler("skip", skip_field))

    # Task action handlers
    app.add_handler(CallbackQueryHandler(start_task, pattern="^start_"))
    app.add_handler(CallbackQueryHandler(done_task, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(cancel_task, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(pending_task, pattern="^pending_"))

    app.add_handler(CallbackQueryHandler(detail_page, pattern="^detail_page_"))
    app.add_handler(CallbackQueryHandler(download_csv, pattern="^download_csv"))

    # Reports & Templates
    app.add_handler(CallbackQueryHandler(reports_callback, pattern="^report_"))
    app.add_handler(CallbackQueryHandler(templates_callback, pattern="^tpl_"))

    app.add_handler(CallbackQueryHandler(priority_selected, pattern="^priority_"))
    app.add_handler(CallbackQueryHandler(deadline_selected, pattern="^deadline_"))

    # Generic menu buttons (must be last among callbacks)
    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=(
                "^(?!priority_|deadline_|detail_page_|download_csv|"
                "start_|done_|cancel_|pending_|report_|tpl_)"
            )
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_task
        )
    )

    logging.info("Task Bot Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
