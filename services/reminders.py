import logging
from datetime import date, datetime, timedelta
from collections import defaultdict

from services.task_service import get_all_user_ids, get_active_tasks, get_all_user_tasks

logger = logging.getLogger(__name__)


def _priority_emoji(p):
    return {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(p, "🟢")


async def morning_today_tasks(context):
    """07:00 — list tasks due today (and overdue active)."""

    today = date.today().isoformat()
    user_ids = get_all_user_ids()

    for uid in user_ids:
        try:
            user_id = int(uid)
        except ValueError:
            continue

        tasks = get_active_tasks(user_id)
        today_list = [t for t in tasks if (t.get("deadline") or "") == today]
        overdue = [
            t for t in tasks
            if t.get("deadline") and t.get("deadline") < today
        ]

        if not today_list and not overdue:
            continue

        lines = ["☀️ صبح بخیر — برنامه امروز\n"]

        if today_list:
            lines.append(f"📌 تسک‌های امروز ({len(today_list)}):")
            for t in sorted(today_list, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("priority"), 3)):
                lines.append(f"• {_priority_emoji(t.get('priority'))} {t.get('title', '-')}")
        else:
            lines.append("📌 تسک با مهلت امروز ندارید.")

        if overdue:
            lines.append(f"\n⚠️ عقب‌افتاده ({len(overdue)}):")
            for t in overdue[:8]:
                lines.append(f"• {_priority_emoji(t.get('priority'))} {t.get('title', '-')} ({t.get('deadline')})")
            if len(overdue) > 8:
                lines.append(f"... و {len(overdue) - 8} مورد دیگر")

        try:
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Morning reminder failed for %s: %s", user_id, e)


async def midday_summary_and_weekly(context):
    """11:00 — today's activity summary + weekly overview."""

    today = date.today()
    today_str = today.isoformat()
    week_start = today - timedelta(days=today.weekday())  # Monday

    user_ids = get_all_user_ids()

    for uid in user_ids:
        try:
            user_id = int(uid)
        except ValueError:
            continue

        all_tasks = get_all_user_tasks(user_id)
        if not all_tasks:
            continue

        # Today completed
        done_today = []
        for t in all_tasks:
            if t.get("status") != "done":
                continue
            completed = (t.get("completed_at") or "")[:10]
            if completed == today_str:
                done_today.append(t)

        active = [t for t in all_tasks if t.get("status") in ("pending", "in_progress")]
        due_today = [t for t in active if (t.get("deadline") or "") == today_str]

        lines = ["📋 خلاصه فعالیت امروز\n"]
        lines.append(f"✅ انجام‌شده امروز: {len(done_today)}")
        if done_today:
            for t in done_today[:6]:
                lines.append(f"  • {t.get('title', '-')}")
            if len(done_today) > 6:
                lines.append(f"  ... و {len(done_today) - 6} مورد")

        lines.append(f"\n📌 باقی‌مانده امروز: {len(due_today)}")
        lines.append(f"📂 کل فعال: {len(active)}")

        # Weekly
        created_week = 0
        done_week = 0
        for t in all_tasks:
            created_s = (t.get("created_at") or "")[:10]
            try:
                created_d = datetime.strptime(created_s, "%Y-%m-%d").date()
                if created_d >= week_start:
                    created_week += 1
            except Exception:
                pass
            if t.get("status") == "done":
                completed_s = (t.get("completed_at") or t.get("created_at") or "")[:10]
                try:
                    completed_d = datetime.strptime(completed_s, "%Y-%m-%d").date()
                    if completed_d >= week_start:
                        done_week += 1
                except Exception:
                    pass

        lines.append("\n📅 گزارش هفتگی (از دوشنبه):")
        lines.append(f"• ایجادشده این هفته: {created_week}")
        lines.append(f"• انجام‌شده این هفته: {done_week}")

        try:
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Midday summary failed for %s: %s", user_id, e)


# Keep old name as alias for safety if referenced elsewhere
async def check_deadline_reminders(context):
    """Legacy alias — prefer morning_today_tasks."""
    await morning_today_tasks(context)
