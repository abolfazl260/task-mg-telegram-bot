import uuid
from datetime import datetime

from services.csv_manager import (
    save_task,
    read_tasks,
    update_task_status
)


def create_task(
        user_id,
        title,
        priority,
        deadline,
        category,
        tags
):

    task_id = str(uuid.uuid4())[:8]

    save_task([

        task_id,
        str(user_id),
        title,
        priority,
        "pending",
        deadline,
        category,
        tags,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

    ])

    return task_id


def get_active_tasks(user_id):

    tasks = read_tasks()

    result = []

    for task in tasks:

        if str(task.get("user_id")).strip() == str(user_id).strip():

            if task.get("status") in [
                "pending",
                "in_progress"
            ]:
                result.append(task)

    return result


def get_all_user_tasks(user_id):
    """All tasks of a user regardless of status."""

    tasks = read_tasks()

    result = []

    for task in tasks:

        if str(task.get("user_id")).strip() == str(user_id).strip():
            result.append(task)

    return result


def get_task_by_id(task_id: str):

    tasks = read_tasks()

    for task in tasks:
        if task.get("id") == task_id:
            return task

    return None


def change_task_status(task_id: str, new_status: str) -> bool:
    """Change task status. Valid: pending, in_progress, done, cancelled"""

    valid = {"pending", "in_progress", "done", "cancelled"}

    if new_status not in valid:
        return False

    return update_task_status(task_id, new_status)
