import csv
import os
from datetime import datetime

FILE_PATH = "data/tasks.csv"

HEADERS = [
    "id",
    "user_id",
    "title",
    "priority",
    "status",
    "deadline",
    "category",
    "tags",
    "description",
    "created_at",
    "completed_at",
    "team_id",
    "assignee_id",
    "assignee_name",
    "assignee_username",
    "assignment_history",
]


def init_csv():

    os.makedirs("data", exist_ok=True)

    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)
        return

    with open(FILE_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        old_fields = list(reader.fieldnames or [])
        rows = list(reader)

    missing = [h for h in HEADERS if h not in old_fields]
    if missing:
        for row in rows:
            for h in HEADERS:
                row.setdefault(h, "")

        with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({h: row.get(h, "") for h in HEADERS})


def save_task(data):
    with open(FILE_PATH, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(data)


def read_tasks():
    if not os.path.exists(FILE_PATH):
        return []

    with open(FILE_PATH, "r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    for row in rows:
        for h in HEADERS:
            row.setdefault(h, "")
    return rows


def _write_all(tasks):
    with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for task in tasks:
            writer.writerow({h: task.get(h, "") for h in HEADERS})


def update_task_status(task_id: str, new_status: str) -> bool:
    if not os.path.exists(FILE_PATH):
        return False

    tasks = read_tasks()
    updated = False

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = new_status
            if new_status == "done":
                task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            elif new_status in ("pending", "in_progress", "cancelled"):
                if new_status != "done":
                    task["completed_at"] = ""
            updated = True
            break

    if not updated:
        return False

    _write_all(tasks)
    return True
