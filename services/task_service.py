import uuid
from datetime import datetime

from services.csv_manager import (
    save_task,
    read_tasks,
    update_task_status
)
from services.team_service import get_user_teams, can_edit, is_member


def create_task(
        user_id,
        title,
        priority,
        deadline,
        category,
        tags,
        description="",
        team_id="",
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
        description or "",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",  # completed_at
        team_id or "",
    ])

    return task_id


def _user_team_ids(user_id):
    return {item["team"]["team_id"] for item in get_user_teams(user_id)}


def get_active_tasks(user_id, team_id=None):
    """
    Active tasks visible to user.
    - If team_id given: only that team's active tasks (must be member).
    - Else: personal (no team) + all teams user belongs to.
    """

    tasks = read_tasks()
    uid = str(user_id).strip()
    result = []

    if team_id:
        if not is_member(team_id, user_id):
            return []
        for task in tasks:
            if (task.get("team_id") or "") == team_id and task.get("status") in ("pending", "in_progress"):
                result.append(task)
        return result

    team_ids = _user_team_ids(user_id)
    for task in tasks:
        if task.get("status") not in ("pending", "in_progress"):
            continue
        tid = (task.get("team_id") or "").strip()
        if tid:
            if tid in team_ids:
                result.append(task)
        elif str(task.get("user_id")).strip() == uid:
            result.append(task)

    return result


def get_all_user_tasks(user_id, team_id=None):
    """All statuses; same visibility rules as get_active_tasks."""

    tasks = read_tasks()
    uid = str(user_id).strip()
    result = []

    if team_id:
        if not is_member(team_id, user_id):
            return []
        for task in tasks:
            if (task.get("team_id") or "") == team_id:
                result.append(task)
        return result

    team_ids = _user_team_ids(user_id)
    for task in tasks:
        tid = (task.get("team_id") or "").strip()
        if tid:
            if tid in team_ids:
                result.append(task)
        elif str(task.get("user_id")).strip() == uid:
            result.append(task)

    return result


def get_team_tasks(team_id: str, active_only=True):
    tasks = read_tasks()
    result = []
    for task in tasks:
        if (task.get("team_id") or "") != team_id:
            continue
        if active_only and task.get("status") not in ("pending", "in_progress"):
            continue
        result.append(task)
    return result


def get_task_by_id(task_id: str):

    tasks = read_tasks()

    for task in tasks:
        if task.get("id") == task_id:
            return task

    return None


def user_can_modify_task(user_id, task: dict) -> bool:
    """Personal task owner OR team editor/owner."""

    if not task:
        return False
    tid = (task.get("team_id") or "").strip()
    if tid:
        return can_edit(tid, user_id)
    return str(task.get("user_id")).strip() == str(user_id).strip()


def change_task_status(task_id: str, new_status: str) -> bool:

    valid = {"pending", "in_progress", "done", "cancelled"}

    if new_status not in valid:
        return False

    return update_task_status(task_id, new_status)


def search_tasks(user_id, query: str):
    """Search in title, category, tags, description (visible tasks)."""

    q = (query or "").strip().lower()
    if not q:
        return []

    result = []
    for task in get_all_user_tasks(user_id):
        blob = " ".join([
            task.get("title") or "",
            task.get("category") or "",
            task.get("tags") or "",
            task.get("description") or "",
        ]).lower()
        if q in blob:
            result.append(task)
    return result


def get_all_user_ids():
    """Distinct user ids that have at least one task (for reminders)."""
    seen = set()
    for task in read_tasks():
        uid = str(task.get("user_id") or "").strip()
        if uid:
            seen.add(uid)
    return list(seen)
