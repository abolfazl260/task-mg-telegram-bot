import logging
import traceback
from datetime import date

from config import ADMIN_IDS
from services.task_service import get_all_user_ids, get_all_user_tasks
from services.user_service import all_users

logger = logging.getLogger(__name__)


def _admin_text_ids():
    return [int(x) for x in ADMIN_IDS if str(x).strip().isdigit()]


async def notify_admins(context, text):
    for admin_id in _admin_text_ids():
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception as exc:
            logger.warning("Admin notification failed for %s: %s", admin_id, exc)


async def notify_new_user(context, user):
    if not user:
        return
    await notify_admins(context, "🆕 کاربر جدید ربات\n\n" f"نام: {user.full_name}\n" f"یوزرنیم: @{user.username or '—'}\n" f"آیدی: {user.id}")


async def daily_admin_report(context):
    users = all_users()
    task_user_ids = set(get_all_user_ids())
    user_ids = {u.get("user_id") for u in users if u.get("user_id")} | task_user_ids
    today = date.today().isoformat()
    lines = ["📊 گزارش روزانه ربات", f"تاریخ: {today}", "", f"👥 تعداد کل کاربران: {len(user_ids)}", "", "📌 استفاده بر اساس کاربر:"]
    if not users:
        lines.append("هنوز داده کاربری ثبت نشده است.")
    for u in sorted(users, key=lambda r: int(r.get("messages_count") or 0), reverse=True):
        uid = u.get("user_id")
        tasks = get_all_user_tasks(uid) if uid else []
        lines.append(
            f"• {u.get('full_name') or uid} (@{u.get('username') or '—'})\n"
            f"  آیدی: {uid} | پیام‌ها: {u.get('messages_count') or 0} | تسک‌ها: {len(tasks)} | منطقه: {u.get('timezone') or 'UTC'}"
        )
    await notify_admins(context, "\n".join(lines[:80]))


async def error_handler(update, context):
    logger.exception("Bot error", exc_info=context.error)
    err = "".join(traceback.format_exception_only(type(context.error), context.error)).strip()
    await notify_admins(context, f"🚨 خطای ربات\n\n{err}\n\nUpdate: {update}")
