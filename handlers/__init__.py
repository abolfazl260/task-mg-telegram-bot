"""Handler bootstrap hooks kept isolated from the application entry point."""

from telegram.ext import Application, CallbackQueryHandler

_original_add_handler = Application.add_handler
_bootstrapped = False


def _bootstrap_application(application: Application) -> None:
    global _bootstrapped
    if _bootstrapped:
        return

    from services.calendar_runtime_extensions import viewer_id
    from services.permission_service import PERMISSION_KANBAN_PDF, has_permission_sync
    import handlers.reports as reports_handler
    from handlers.kanban_pdf import (
        access_settings_callback,
        install_access_ui,
        kanban_pdf_callback,
    )

    original_reports_keyboard = reports_handler.reports_menu_keyboard

    def reports_menu_keyboard_with_permission():
        markup = original_reports_keyboard()
        if not has_permission_sync(viewer_id(), PERMISSION_KANBAN_PDF):
            return markup
        rows = [list(row) for row in markup.inline_keyboard]
        if not any(button.callback_data == "report_kanban_pdf" for row in rows for button in row):
            rows.append([__import__("telegram").InlineKeyboardButton("📄 ایجاد PDF کانبان برد", callback_data="report_kanban_pdf")])
        return __import__("telegram").InlineKeyboardMarkup(rows)

    reports_handler.reports_menu_keyboard = reports_menu_keyboard_with_permission
    install_access_ui()

    _original_add_handler(
        application,
        CallbackQueryHandler(kanban_pdf_callback, pattern="^report_kanban_pdf$"),
        group=-50,
    )
    _original_add_handler(
        application,
        CallbackQueryHandler(access_settings_callback, pattern="^(settings_permissions|perm_toggle_[0-9]+)$"),
        group=-50,
    )
    _bootstrapped = True


def _add_handler_with_bootstrap(self, handler, group=0):
    _bootstrap_application(self)
    return _original_add_handler(self, handler, group)


Application.add_handler = _add_handler_with_bootstrap
