    app.add_handler(CallbackQueryHandler(integration_callback, pattern="^int_"))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!priority_|deadline_|category_pick_|category_skip|tags_|description_skip|detail_page_|download_csv|start_|done_|cancel_|pending_|take_|assign_|owner_|asg_|chg_|task_details_|task_history_|comment_add_|comment_cancel_|report_|tpl_|sort_|share_cat_|import_|team_|habit_|donate_|custombot_|int_)"))
    # Do not register handle_tag_text as a catch-all handler here. save_task
    # already delegates tag input to handle_tag_text. A second catch-all
    # MessageHandler at the same group would consume every normal text message
    # before save_task can process the title and advance to priority.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_task), group=0)
    app.add_error_handler(error_handler)
    return app


def main():
    # init_db() is handled by PTB's async post_init lifecycle.
    # Do not create/access an event loop here: Python 3.13 deprecates
    # asyncio.get_event_loop() when no current loop exists. PTB creates and
    # manages the loop for run_polling(), while asyncio.run() owns the loop
    # for the multi-bot path below.
    apps = [build_application(profile) for profile in BOT_PROFILES]
    logger.info("Starting %s bot application(s): %s", len(apps), ", ".join(p.key for p in BOT_PROFILES))

    if len(apps) == 1:
        apps[0].run_polling(allowed_updates=[*Update.ALL_TYPES, "guest_message"])
    else:
        asyncio.run(run_applications(apps))


if __name__ == "__main__":
    main()
