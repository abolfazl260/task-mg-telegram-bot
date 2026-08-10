    app.add_handler(CallbackQueryHandler(team_callback, pattern="^team_"))
    app.add_handler(CallbackQueryHandler(handle_habit_callback, pattern="^habit_"))
    app.add_handler(CallbackQueryHandler(custom_bot_callback, pattern="^custombot_"))
    app.add_handler(CallbackQueryHandler(donate_callback, pattern="^donate_(10|40|100)$"))
    app.add_handler(CallbackQueryHandler(integration_callback, pattern="^int_"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!priority_|deadline_|category_pick_|category_skip|tags_|description_skip|detail_page_|download_csv|start_|done_|cancel_|pending_|take_|assign_|owner_|asg_|chg_|task_details_|task_history_|comment_add_|report_|tpl_|sort_|share_cat_|import_|team_|habit_|donate_|custombot_|int_)"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_tag_text), group=0)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, save_task))
    app.add_error_handler(error_handler)
    return app


def main():
    # Initialize the single SQLite database before any application is created.
    # Legacy init_* functions are intentionally not called here: they are kept
    # only as compatibility facades and must not create CSV/JSON stores.
    asyncio.run(init_db())
    apps = [build_application(profile) for profile in BOT_PROFILES]
    logger.info("Starting %s bot application(s): %s", len(apps), ", ".join(p.key for p in BOT_PROFILES))

    # Python 3.13 no longer creates a default event loop automatically.
    # python-telegram-bot's run_polling() accesses the current loop before
    # starting it, so explicitly create and register one for compatibility.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    if len(apps) == 1:
        apps[0].run_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])
    else:
        asyncio.run(run_applications(apps))


if __name__ == "__main__":
    main()
