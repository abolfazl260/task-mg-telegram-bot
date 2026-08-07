"""Jira Cloud connection and bidirectional task synchronization."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from urllib import error, parse, request

from bot_context import get_current_bot_key
from services.csv_manager import _write_all, read_tasks

BASE_DIR = Path(__file__).resolve().parent.parent
CONNECTIONS_FILE = BASE_DIR / "data" / "jira_connections.json"
LINKS_FILE = BASE_DIR / "data" / "jira_task_links.json"
_LOCK = threading.Lock()

STATUS_TO_JIRA = {"pending": ("pending", "to do", "open", "new"), "in_progress": ("in progress", "in-progress", "started"), "done": ("done", "closed", "resolved"), "cancelled": ("cancelled", "canceled", "closed")}


def _load_json(path: Path, default):
    if not path.exists(): return default
    try:
        data = json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data, type(default)) else default
    except Exception: return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); os.replace(tmp, path)
    try: os.chmod(path, 0o600)
    except OSError: pass


def _load_connections() -> list[dict]: return _load_json(CONNECTIONS_FILE, [])
def _save_connections(items: list[dict]) -> None: _save_json(CONNECTIONS_FILE, items)
def _load_links() -> list[dict]: return _load_json(LINKS_FILE, [])
def _save_links(items: list[dict]) -> None: _save_json(LINKS_FILE, items)


def get_connection(user_id: int | str, bot_key: str | None = None) -> dict | None:
    bot_key = bot_key or get_current_bot_key(); uid = str(user_id)
    return next((x for x in _load_connections() if x.get("bot_key") == bot_key and str(x.get("user_id")) == uid), None)


def save_connection(user_id: int | str, base_url: str, email: str, api_token: str, project_key: str, issue_type: str = "Task", account_id: str = "") -> dict:
    base_url = base_url.strip().rstrip("/")
    if not re.match(r"^https://[^/]+$", base_url): raise ValueError("Jira URL must be an HTTPS origin such as https://company.atlassian.net")
    if not email.strip() or not api_token.strip() or not project_key.strip(): raise ValueError("Jira URL, email, API token and project key are required.")
    connection = {"bot_key": get_current_bot_key(), "user_id": str(user_id), "base_url": base_url, "email": email.strip(), "api_token": api_token.strip(), "project_key": project_key.strip().upper(), "issue_type": issue_type.strip() or "Task", "account_id": account_id, "connected_at": datetime.now().isoformat(timespec="seconds"), "last_sync_at": ""}
    items = [x for x in _load_connections() if not (x.get("bot_key") == connection["bot_key"] and str(x.get("user_id")) == connection["user_id"])]
    items.append(connection)
    with _LOCK: _save_connections(items)
    return connection


def disconnect(user_id: int | str) -> bool:
    bot_key = get_current_bot_key(); items = _load_connections(); new_items = [x for x in items if not (x.get("bot_key") == bot_key and str(x.get("user_id")) == str(user_id))]
    if len(new_items) == len(items): return False
    with _LOCK: _save_connections(new_items)
    return True


def _request_json(connection: dict, method: str, path: str, payload: dict | None = None, query: dict | None = None) -> dict | list:
    url = connection["base_url"] + path
    if query: url += "?" + parse.urlencode(query)
    credentials = f"{connection['email']}:{connection['api_token']}".encode(); token = base64.b64encode(credentials).decode(); body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method=method.upper(), headers={"Authorization": f"Basic {token}", "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8"); return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]; raise RuntimeError(f"Jira API {exc.code}: {detail}") from exc


def validate_connection(base_url: str, email: str, api_token: str, project_key: str) -> dict:
    test = {"base_url": base_url.rstrip("/"), "email": email, "api_token": api_token, "project_key": project_key}
    myself = _request_json(test, "GET", "/rest/api/3/myself")
    _request_json(test, "GET", f"/rest/api/3/project/{parse.quote(project_key, safe='')}")
    return myself if isinstance(myself, dict) else {}


def _jira_due_date(deadline: str) -> str | None:
    match = re.search(r"(20\d\d[-/]\d{1,2}[-/]\d{1,2})", (deadline or "").strip()); return match.group(1).replace("/", "-") if match else None


def _task_to_fields(task: dict, connection: dict) -> dict:
    fields = {"project": {"key": connection["project_key"]}, "summary": task.get("title") or "Telegram Task", "issuetype": {"name": connection.get("issue_type") or "Task"}, "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": task.get("description") or ""}]}]}}
    due = _jira_due_date(task.get("deadline", ""))
    if due: fields["duedate"] = due
    return fields


def _local_hash(task: dict) -> str:
    payload = {"title": task.get("title", ""), "description": task.get("description", ""), "status": task.get("status", ""), "priority": task.get("priority", ""), "deadline": task.get("deadline", "")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _linked_task(tasks: list[dict], jira_key: str) -> dict | None:
    for task in tasks:
        if task.get("jira_key") == jira_key: return task
    link = next((x for x in _load_links() if x.get("bot_key") == get_current_bot_key() and x.get("jira_key") == jira_key), None)
    return next((t for t in tasks if t.get("id") == link.get("task_id")), None) if link else None


def _attach_links(tasks: list[dict]) -> None:
    links = _load_links(); bot = get_current_bot_key(); by_id = {t.get("id"): t for t in tasks}
    for link in links:
        if link.get("bot_key") == bot and link.get("task_id") in by_id:
            by_id[link["task_id"]]["jira_key"] = link.get("jira_key", ""); by_id[link["task_id"]]["jira_sync_hash"] = link.get("sync_hash", "")


def _persist_link(task: dict, jira_key: str, sync_hash: str) -> None:
    links = _load_links(); bot = get_current_bot_key(); task_id = task.get("id")
    links = [x for x in links if not (x.get("bot_key") == bot and x.get("task_id") == task_id)]
    links.append({"bot_key": bot, "task_id": task_id, "jira_key": jira_key, "sync_hash": sync_hash, "updated_at": datetime.now().isoformat(timespec="seconds")}); _save_links(links)


def create_issue_for_task(task: dict, user_id: int | str) -> str | None:
    connection = get_connection(user_id)
    if not connection or task.get("jira_key"): return None
    result = _request_json(connection, "POST", "/rest/api/3/issue", {"fields": _task_to_fields(task, connection)})
    key = result.get("key") if isinstance(result, dict) else None
    if key:
        if connection.get("account_id"):
            try: _request_json(connection, "PUT", f"/rest/api/3/issue/{parse.quote(key, safe='')}/assignee", {"accountId": connection["account_id"]})
            except Exception: pass
        _persist_link(task, key, _local_hash(task))
    return key


def _jira_status_name(status: str) -> str: return STATUS_TO_JIRA.get(status, ("pending",))[0]


def _find_transition(connection: dict, issue_key: str, local_status: str) -> str | None:
    data = _request_json(connection, "GET", f"/rest/api/3/issue/{parse.quote(issue_key, safe='')}/transitions"); wanted = {x.lower() for x in STATUS_TO_JIRA.get(local_status, ())}
    for transition in data.get("transitions", []) if isinstance(data, dict) else []:
        name = (transition.get("name") or "").lower(); to_name = ((transition.get("to") or {}).get("name") or "").lower()
        if name in wanted or to_name in wanted or _jira_status_name(local_status) in name: return transition.get("id")
    return None


def update_issue_from_task(task: dict, user_id: int | str) -> bool:
    connection = get_connection(user_id); key = task.get("jira_key")
    if not connection or not key: return False
    fields = _task_to_fields(task, connection); fields.pop("project", None); fields.pop("issuetype", None)
    _request_json(connection, "PUT", f"/rest/api/3/issue/{parse.quote(key, safe='')}", {"fields": fields})
    transition_id = _find_transition(connection, key, task.get("status", "pending"))
    if transition_id: _request_json(connection, "POST", f"/rest/api/3/issue/{parse.quote(key, safe='')}/transitions", {"transition": {"id": transition_id}})
    _persist_link(task, key, _local_hash(task)); return True


def _map_jira_status(name: str) -> str:
    value = (name or "").lower()
    if any(x in value for x in ("done", "closed", "resolved", "complete")): return "done"
    if any(x in value for x in ("cancel", "rejected")): return "cancelled"
    if any(x in value for x in ("progress", "started", "development")): return "in_progress"
    return "pending"


def _description_text(issue: dict) -> str:
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text": return node.get("text", "")
            return "".join(walk(x) for x in node.get("content", []))
        if isinstance(node, list): return "".join(walk(x) for x in node)
        return ""
    return walk(issue.get("fields", {}).get("description"))


def _apply_issue_to_task(task: dict, issue: dict) -> bool:
    fields = issue.get("fields", {}); changed = False; summary = fields.get("summary") or task.get("title"); description = _description_text(issue); status = _map_jira_status((fields.get("status") or {}).get("name", ""))
    if summary != task.get("title"): task["title"] = summary; changed = True
    if description != (task.get("description") or ""): task["description"] = description; changed = True
    if status != task.get("status"): task["status"] = status; task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M") if status == "done" else ""; changed = True
    due = fields.get("duedate") or ""
    if due != (task.get("deadline") or ""): task["deadline"] = due; changed = True
    priority = (fields.get("priority") or {}).get("name", "").lower(); mapped_priority = "high" if "high" in priority or "highest" in priority else "low" if "low" in priority else "medium"
    if mapped_priority != task.get("priority"): task["priority"] = mapped_priority; changed = True
    return changed


def _jira_issues_for_user(connection: dict) -> list[dict]:
    links = [x.get("jira_key") for x in _load_links() if x.get("bot_key") == get_current_bot_key() and x.get("jira_key")]
    linked_clause = " OR key in (" + ",".join(links) + ")" if links else ""
    jql = f"project = {connection['project_key']} AND (assignee = currentUser(){linked_clause}) ORDER BY updated DESC"
    data = _request_json(connection, "GET", "/rest/api/3/search/jql", query={"jql": jql, "maxResults": 100, "fields": "summary,description,status,duedate,priority,updated"})
    return data.get("issues", []) if isinstance(data, dict) else []


def sync_connection(connection: dict) -> int:
    tasks = read_tasks(); _attach_links(tasks); by_key = {t.get("jira_key"): t for t in tasks if t.get("jira_key")}; changed = 0
    for issue in _jira_issues_for_user(connection):
        key = issue.get("key"); task = by_key.get(key) or _linked_task(tasks, key)
        if task:
            task["jira_key"] = key
            if _apply_issue_to_task(task, issue): changed += 1
        else:
            fields = issue.get("fields", {}); task = {"id": f"JIRA-{key}", "user_id": str(connection["user_id"]), "title": fields.get("summary") or key, "priority": "high" if "high" in ((fields.get("priority") or {}).get("name", "").lower()) else "medium", "status": _map_jira_status((fields.get("status") or {}).get("name", "")), "deadline": fields.get("duedate") or "", "category": "Jira", "tags": "jira", "description": _description_text(issue), "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "completed_at": "", "team_id": "", "assignee_id": "", "assignee_name": "", "assignee_username": "", "assignment_history": "", "comments": "", "jira_key": key}
            tasks.append(task); by_key[key] = task; changed += 1
        _persist_link(task, key, _local_hash(task))
    for task in list(tasks):
        if str(task.get("user_id")) != str(connection["user_id"]): continue
        try:
            if not task.get("jira_key"):
                key = create_issue_for_task(task, connection["user_id"])
                if key: task["jira_key"] = key
            elif task.get("jira_sync_hash") != _local_hash(task): update_issue_from_task(task, connection["user_id"])
        except Exception: continue
    if changed: _write_all(tasks)
    return changed


def sync_all_connections(bot_key: str | None = None) -> tuple[int, int]:
    bot_key = bot_key or get_current_bot_key(); total = 0; connections = [x for x in _load_connections() if x.get("bot_key") == bot_key]
    for connection in connections:
        try: total += sync_connection(connection); connection["last_sync_at"] = datetime.now().isoformat(timespec="seconds")
        except Exception: continue
    if connections:
        all_items = _load_connections()
        for item in all_items:
            for updated in connections:
                if item.get("bot_key") == updated.get("bot_key") and str(item.get("user_id")) == str(updated.get("user_id")): item["last_sync_at"] = updated.get("last_sync_at", "")
        _save_connections(all_items)
    return total, len(connections)
