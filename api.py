from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import API_CORS_ORIGINS
from services.csv_manager import init_csv
from services.task_service import (
    change_task_status,
    create_task,
    get_active_tasks,
    get_all_user_tasks,
    get_task_by_id,
    user_can_modify_task,
)
from services.web_app_auth import TelegramWebAppAuthError, validate_telegram_init_data


app = FastAPI(title="TaskMG Telegram Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    deadline: str = ""
    category: str = ""
    tags: str = ""
    description: str = ""


class TaskStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|done|cancelled)$")


@app.on_event("startup")
def startup():
    init_csv()


def current_telegram_user(authorization: str = Header(default="")) -> dict:
    scheme, _, init_data = authorization.partition(" ")
    if scheme.lower() != "tma" or not init_data:
        raise HTTPException(status_code=401, detail="Authorization header must be: tma <Telegram initData>")

    try:
        return validate_telegram_init_data(init_data)
    except TelegramWebAppAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def serialize_task(task: dict) -> dict:
    return {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "priority": task.get("priority", ""),
        "status": task.get("status", ""),
        "deadline": task.get("deadline", ""),
        "category": task.get("category", ""),
        "tags": task.get("tags", ""),
        "description": task.get("description", ""),
        "created_at": task.get("created_at", ""),
        "completed_at": task.get("completed_at", ""),
        "team_id": task.get("team_id", ""),
        "assignee_id": task.get("assignee_id", ""),
        "assignee_name": task.get("assignee_name", ""),
        "assignee_username": task.get("assignee_username", ""),
    }


@app.get("/api/me")
def me(user: dict = Depends(current_telegram_user)):
    return {"user": user}


@app.get("/api/tasks")
def list_tasks(
    status: str = Query("active", pattern="^(active|all)$"),
    user: dict = Depends(current_telegram_user),
):
    user_id = user["id"]
    tasks = get_active_tasks(user_id) if status == "active" else get_all_user_tasks(user_id)
    return {"tasks": [serialize_task(task) for task in tasks]}


@app.post("/api/tasks", status_code=201)
def add_task(payload: TaskCreateRequest, user: dict = Depends(current_telegram_user)):
    task_id = create_task(
        user_id=user["id"],
        title=payload.title.strip(),
        priority=payload.priority,
        deadline=payload.deadline.strip(),
        category=payload.category.strip(),
        tags=payload.tags.strip(),
        description=payload.description.strip(),
    )
    task = get_task_by_id(task_id)
    return {"task": serialize_task(task or {"id": task_id})}


@app.patch("/api/tasks/{task_id}/status")
def update_task_status(
    task_id: str,
    payload: TaskStatusRequest,
    user: dict = Depends(current_telegram_user),
):
    task = get_task_by_id(task_id)
    if not task or not user_can_modify_task(user["id"], task):
        raise HTTPException(status_code=404, detail="Task not found")

    if not change_task_status(task_id, payload.status):
        raise HTTPException(status_code=400, detail="Task status was not updated")

    updated = get_task_by_id(task_id)
    return {"task": serialize_task(updated or task)}
