import io
import csv
import jdatetime
from datetime import datetime

from services.task_service import get_active_tasks


def build_csv_bytes(user_id):
    """Build a CSV file of active tasks and return (BytesIO, count)."""

    tasks = get_active_tasks(user_id)

    priority_map = {
        "high": "بالا",
        "medium": "متوسط",
        "low": "پایین",
    }

    status_map = {
        "pending": "در انتظار",
        "in_progress": "در حال انجام",
        "done": "انجام شده",
        "cancelled": "لغو شده",
    }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ردیف",
        "شناسه",
        "عنوان",
        "دسته‌بندی",
        "برچسب",
        "اولویت",
        "مهلت (میلادی)",
        "مهلت (شمسی)",
        "وضعیت",
        "توضیح",
        "تاریخ ثبت",
    ])

    for index, task in enumerate(tasks, start=1):

        deadline = task.get("deadline", "-")

        jalali_date = "-"
        try:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            jalali_date = (
                jdatetime.date
                .fromgregorian(date=deadline_date)
                .strftime("%Y/%m/%d")
            )
        except Exception:
            jalali_date = "-"

        writer.writerow([
            index,
            task.get("id", "-"),
            task.get("title", "-"),
            task.get("category", "-"),
            task.get("tags", "-"),
            priority_map.get(task.get("priority"), "-"),
            deadline,
            jalali_date,
            status_map.get(task.get("status"), "-"),
            task.get("description", "") or "-",
            task.get("created_at", "-"),
        ])

    data = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(data)
    buffer.seek(0)

    return buffer, len(tasks)
