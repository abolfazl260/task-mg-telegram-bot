import logging
from datetime import date, timedelta

from services.task_service import get_all_user_ids, get_active_tasks

logger = logging.getLogger(__name__)


async def check_deadline_reminders(context):
    """Job: notify users about tasks due tomorrow."""

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    user_ids = get_all_user_ids()

    for uid in user_ids:
        try:
            user_id = int(uid)
        except ValueError:
            continue

        tasks = get_active_tasks(user_id)
        due = [t for t in tasks if (t.get("deadline") or "") == tomorrow]

        if not due:
            continue

        lines = [
            "⏰ یادآوری: فردا مهلت این تسک‌هاست:\n"
        ]
        for t in due:
            pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(
                t.get("priority"), "🟢"
            )
            lines.append(f"• {pr} {t.get('title', '-')}")

        text = "\n".join(lines)

        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.warning("Reminder failed for %s: %s", user_id, e)
