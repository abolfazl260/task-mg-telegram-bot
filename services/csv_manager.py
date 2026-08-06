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
    "created_at"
]


def init_csv():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(FILE_PATH):

        with open(
            FILE_PATH,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)
            writer.writerow(HEADERS)


def save_task(data):

    with open(
        FILE_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)
        writer.writerow(data)


def read_tasks():

    if not os.path.exists(FILE_PATH):
        return []

    with open(
        FILE_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        return list(reader)


def update_task_status(task_id: str, new_status: str) -> bool:
    """Update status of a task by id. Returns True if updated."""

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

    with open(
        FILE_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(tasks)

    return True
