import logging

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
    download_excel
)

from services.csv_manager import init_csv


logging.basicConfig(
    level=logging.INFO
)


def main():

    init_csv()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            detail_page,
            pattern="^detail_page_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            download_excel,
            pattern="^download_excel"
        )
    )

    app.add_handler(
        CommandHandler(
            "add",
            add_task
        )
    )

    app.add_handler(
        CommandHandler(
            "tasks",
            list_tasks
        )
    )

    app.add_handler(
        CommandHandler(
            "skip",
            skip_field
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            priority_selected,
            pattern="^priority_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            deadline_selected,
            pattern="^deadline_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern="^(?!priority_|deadline_|detail_page_|download_excel)"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            save_task
        )
    )

    logging.info(
        "Task Bot Started..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()
