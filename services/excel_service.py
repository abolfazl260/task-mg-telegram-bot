import io
import jdatetime

from services.task_service import get_active_tasks

import pandas as pd


def build_excel_bytes(user_id):

    tasks = get_active_tasks(user_id)

    rows = []
    for index, task in enumerate(tasks, start=1):

        deadline = task.get("deadline", "-")

        jalali_date = "-"
        try:
            jalali_date = (
                jdatetime.date
                .fromgregorian(
                    date=pd.to_datetime(
                        deadline
                    ).date()
                )
                .strftime("%Y/%m/%d")
            )
        except Exception:
            jalali_date = "-"

        priority_map = {
            "high": "🔴 بالا",
            "medium": "🟠 متوسط",
            "low": "🟢 پایین",
        }

        status_map = {
            "pending": "⏳ در انتظار",
            "in_progress": "🚀 در حال انجام",
            "done": "✅ انجام شده",
            "cancelled": "❌ لغو شده",
        }

        rows.append({
            "ردیف": index,
            "عنوان": task.get("title", "-"),
            "دسته‌بندی": task.get("category", "-"),
            "برچسب": task.get("tags", "-"),
            "اولویت": priority_map.get(
                task.get("priority"),
                "-"
            ),
            "مهلت (میلادی)": deadline,
            "مهلت (شمسی)": jalali_date,
            "وضعیت": status_map.get(
                task.get("status"),
                "-"
            ),
            "تاریخ ثبت": task.get("created_at", "-"),
        })

    df = pd.DataFrame(rows)

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="تسک‌ها"
        )

    buffer.seek(0)

    return buffer, len(tasks)
