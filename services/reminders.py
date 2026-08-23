import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.task_service import get_all_user_ids_async, get_active_tasks_async, get_all_user_tasks_async
from services.user_service import get_user_timezone
from services.habit_service import (
    get_all_habit_user_ids_async,
    get_logs_async,
    get_user_habits_async,
    is_habit_due_on,
    stats_for_habit_async,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def _priority_emoji(p):
    return {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(p, "🟢")


def _user_now(user_id):
    return datetime.now(ZoneInfo(get_user_timezone(user_id)))


def _is_user_local_time(user_id, hour, minute):
    now = _user_now(user_id)
    return now.hour == hour and now.minute == minute


async def morning_today_tasks(context):
    """07:00 — list tasks due today (and overdue active)."""
    user_ids = await get_all_user_ids_async()
    for uid in user_ids:
        try:
            user_id = int(uid)
        except (ValueError, TypeError):
            continue
        if not _is_user_local_time(user_id, 7, 0):
            continue
        local_today = _user_now(user_id).date().isoformat()
        tasks = await get_active_tasks_async(user_id)
        today_list = [t for t in tasks if (t.get("deadline") or "") == local_today]
        overdue = [t for t in tasks if t.get("deadline") and t.get("deadline") < local_today]
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
    user_ids = await get_all_user_ids_async()
    for uid in user_ids:
        try:
            user_id = int(uid)
        except (ValueError, TypeError):
            continue
        if not _is_user_local_time(user_id, 11, 0):
            continue
        today = _user_now(user_id).date()
        today_str = today.isoformat()
        week_start = today - timedelta(days=today.weekday())
        all_tasks = await get_all_user_tasks_async(user_id)
        if not all_tasks:
            continue
        done_today = []
        for t in all_tasks:
            if t.get("status") != "done":
                continue
            completed = (t.get("completed_at") or "")[:10]
            if completed == today_str:
                done_today.append(t)
        active = [t for t in all_tasks if t.get("status") in ("pending", "in_progress")]
        due_today = [t for t in active if (t.get("deadline") or "") == today_str]
        lines = ["📋 خلاصه فعالیت امروز\n", f"✅ انجام‌شده امروز: {len(done_today)}"]
        if done_today:
            for t in done_today[:6]:
                lines.append(f"  • {t.get('title', '-')}")
            if len(done_today) > 6:
                lines.append(f"  ... و {len(done_today) - 6} مورد")
        lines.append(f"\n📌 باقی‌مانده امروز: {len(due_today)}")
        lines.append(f"📂 کل فعال: {len(active)}")
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


async def check_deadline_reminders(context):
    """Legacy alias — prefer morning_today_tasks."""
    await morning_today_tasks(context)


def _habit_reminder_times(value):
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


async def habit_reminders(context):
    """Every minute — send habit reminders that match the current HH:MM."""
    for uid in await get_all_habit_user_ids_async():
        try:
            user_id = int(uid)
        except (ValueError, TypeError):
            continue
        user_now = _user_now(user_id)
        now_time = user_now.strftime("%H:%M")
        for habit in await get_user_habits_async(user_id, active_only=True):
            if not is_habit_due_on(habit):
                continue
            if now_time not in _habit_reminder_times(habit.get("reminder_time")):
                continue
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ انجام دادم", callback_data=f"habit_done_{habit['id']}")],
                [InlineKeyboardButton("⏳ بعداً", callback_data="habit_menu")],
            ])
            try:
                await context.bot.send_message(chat_id=user_id, text=f"⏰ یادآوری عادت\n\nزمان انجام:\n\n{habit.get('title', '—')}\n\nآیا انجام شد؟", reply_markup=keyboard)
            except Exception as e:
                logger.warning("Habit reminder failed for %s: %s", user_id, e)


async def weekly_habit_reports(context):
    """Friday — send automatic weekly habit report."""
    for uid in await get_all_habit_user_ids_async():
        try:
            user_id = int(uid)
        except (ValueError, TypeError):
            continue
        if _user_now(user_id).weekday() != 4 or not _is_user_local_time(user_id, 18, 0):
            continue
        end = _user_now(user_id).date()
        start = end - timedelta(days=6)
        habits = await get_user_habits_async(user_id, active_only=True)
        if not habits:
            continue
        logs = [log for log in await get_logs_async(user_id=user_id) if start.isoformat() <= log.get("done_date", "") <= end.isoformat()]
        counts = {habit["id"]: 0 for habit in habits}
        for log in logs:
            if log.get("habit_id") in counts:
                counts[log["habit_id"]] += 1
        done = sum(counts.values())
        missed = max(0, len(habits) * 7 - done)
        best = max(habits, key=lambda h: counts.get(h["id"], 0))
        weak = min(habits, key=lambda h: counts.get(h["id"], 0))
        record = max(habits, key=lambda h: (await stats_for_habit_async(h))["best"])
        record_stats = await stats_for_habit_async(record)
        text = (
            "📊 گزارش هفتگی عادت‌ها\n\n"
            "عملکرد هفته گذشته:\n\n"
            f"✅ انجام شده:\n{done} بار\n\n"
            f"❌ انجام نشده:\n{missed} بار\n\n"
            "بهترین عادت هفته:\n\n"
            f"{best.get('title')}\n{counts.get(best['id'], 0)} روز از 7 روز\n\n"
            "نیاز به بهبود:\n\n"
            f"{weak.get('title')}\n{counts.get(weak['id'], 0)} روز از 7 روز\n\n"
            "🔥 بهترین رکورد:\n\n"
            f"{record.get('title')}:\n{record_stats['best']} روز\n\n"
            "ادامه بده 💪"
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.warning("Weekly habit report failed for %s: %s", user_id, e)
