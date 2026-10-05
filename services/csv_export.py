import io
import csv
import jdatetime
from datetime import datetime

from services.task_service import get_active_tasks, get_active_tasks_async


def _build_csv_bytes(tasks):
    """Build a CSV file from a task collection and return (BytesIO, count)."""

    priority_map = {
        "high": "high",
        "medium": "medium",
        "low": "low",
    }

    status_map = {
        "pending": "pending",
        "in_progress": "in_progress",
        "done": "done",
        "cancelled": "cancelled",
    }

    output = io.StringIO()
    writer = csv.writer(output)

    # English headers — do not change
    writer.writerow([
        "id",
        "title",
        "priority",
        "status",
        "deadline",
        "deadline_jalali",
        "category",
        "tags",
        "description",
        "created_at",
    ])

    for task in tasks:
        deadline = task.get("deadline") or ""
        jalali_date = ""
        try:
            if deadline:
                deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                jalali_date = (
                    jdatetime.date
                    .fromgregorian(date=deadline_date)
                    .strftime("%Y/%m/%d")
                )
        except Exception:
            jalali_date = ""

        writer.writerow([
            task.get("id", ""),
            task.get("title", ""),
            priority_map.get(task.get("priority"), task.get("priority") or ""),
            status_map.get(task.get("status"), task.get("status") or ""),
            deadline,
            jalali_date,
            task.get("category") or "",
            task.get("tags") or "",
            task.get("description") or "",
            task.get("created_at") or "",
        ])

    data = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(data)
    buffer.seek(0)

    return buffer, len(tasks)


async def build_csv_bytes_async(user_id):
    return _build_csv_bytes(await get_active_tasks_async(user_id))


def build_csv_bytes(user_id):
    """Backward-compatible synchronous export API."""
    return _build_csv_bytes(get_active_tasks(user_id))
