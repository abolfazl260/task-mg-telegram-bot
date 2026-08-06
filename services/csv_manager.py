import csv
import os

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
]


def init_csv():

    os.makedirs("data", exist_ok=True)

    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(HEADERS)
        return

    # migrate old CSV that lacks description column
    with open(FILE_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        old_fields = reader.fieldnames or []
        rows = list(reader)

    if "description" not in old_fields:
        for row in rows:
            row.setdefault("description", "")

        with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                # ensure all keys exist
                out = {h: row.get(h, "") for h in HEADERS}
                writer.writerow(out)


def save_task(data):
    """data is a list matching HEADERS order."""

    with open(FILE_PATH, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(data)


def read_tasks():

    if not os.path.exists(FILE_PATH):
        return []

    with open(FILE_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    # normalize missing description
    for row in rows:
        row.setdefault("description", "")

    return rows


def update_task_status(task_id: str, new_status: str) -> bool:

    if not os.path.exists(FILE_PATH):
        return False

    tasks = read_tasks()
    updated = False

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = new_status
            updated = True
            break

    if not updated:
        return False

    with open(FILE_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for task in tasks:
            out = {h: task.get(h, "") for h in HEADERS}
            writer.writerow(out)

    return True
