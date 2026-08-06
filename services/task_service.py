import uuid
from datetime import datetime

from services.csv_manager import (
    save_task,
    read_tasks
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

        print(task)

        if str(task.get("user_id")).strip() == str(user_id).strip():

            if task.get("status") in [
                "pending",
                "in_progress"
            ]:
                result.append(task)

    return result