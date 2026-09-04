"""Token-authenticated task management routes backed by existing web report tokens."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote, urlparse

from .report_tokens import resolve_report_token
from .tasks_api import WebAppTaskAccessError, get_task, list_tasks, create_task, update_task, change_status
from services.task_service import get_task_comments_async, get_assignment_history_async

STATIC_DIR = Path(__file__).resolve().parent / "static"

def _json(h, status, payload):
    body = json.dumps(payload, ensure_ascii=False, default=str).encode()
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

def _html(h, status, body):
    body = body.encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "text/html; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

def _body(h):
    length = int(h.headers.get("Content-Length", "0") or 0)
    if length > 64 * 1024:
        raise ValueError("request_too_large")
    data = json.loads((h.rfile.read(length) if length else b"{}").decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("invalid_json")
    return data

def _token_from_path(path: str):
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"tasks", "task"}:
        return parts[1]
    return ""

def _auth(token: str):
    record = resolve_report_token(token)
    if not record:
        raise WebAppTaskAccessError("invalid_or_expired_dashboard_token")
    return record

async def _full_task(user_id, task_id, bot_key, runtime):
    task = await get_task(user_id, task_id, bot_key)
    if not task:
        return None
    comments = await get_task_comments_async(task_id)
    assignment_history = await get_assignment_history_async(task_id)
    return {**task, "comments": comments, "assignment_history": assignment_history}

def handle_public_task_get(handler):
    path = urlparse(handler.path).path
    if not (path.startswith("/tasks/") or path.startswith("/task/")):
        return False
    token = _token_from_path(path)
    if not token:
        _json(handler, 404, {"error": "not_found"})
        return True
    _auth(token)
    if path == f"/tasks/{quote(token, safe='')}":
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        bridge = f"""<script>
window.__dashboardTaskToken={json.dumps(token)};
const __token=window.__dashboardTaskToken;
const __origFetch=window.fetch.bind(window);
window.fetch=(input,init)=>{{
  const u=typeof input==='string'?input:input.url;
  if(u.startsWith('/api/tasks')){{
    const suffix=u.slice('/api/tasks'.length);
    const target='/api/public-tasks/'+encodeURIComponent(__token)+suffix;
    return __origFetch(target,init);
  }}
  return __origFetch(input,init);
}};
const __q=new URLSearchParams(location.search);__q.set('bot_key',__token);history.replaceState(null,'',location.pathname+'?'+__q.toString());
document.addEventListener('click',e=>{{const card=e.target.closest('[data-task-id]');if(card){{e.preventDefault();e.stopImmediatePropagation();location.href='/task/'+encodeURIComponent(__token)+'/'+encodeURIComponent(card.dataset.taskId);}}}},true);
</script>"""
        html = html.replace('<script src="/static/app.js"></script>', bridge + '<script src="/static/app.js"></script>')
        _html(handler, 200, html)
        return True
    if path.startswith('/task/'):
        parts = [p for p in path.split('/') if p]
        if len(parts) != 3 or parts[1] != token:
            _json(handler, 404, {"error": "not_found"})
            return True
        html = (STATIC_DIR / "task.html").read_text(encoding="utf-8")
        task_id = parts[2]
        bridge = f"""<script>
window.__dashboardTaskToken={json.dumps(token)};
window.__dashboardTaskId={json.dumps(task_id)};
const __token=window.__dashboardTaskToken;
const __origFetch=window.fetch.bind(window);
window.fetch=(input,init)=>{{
  const u=typeof input==='string'?input:input.url;
  if(u.startsWith('/api/tasks')){{
    const suffix=u.slice('/api/tasks'.length);
    const target='/api/public-tasks/'+encodeURIComponent(__token)+suffix;
    return __origFetch(target,init);
  }}
  return __origFetch(input,init);
}};
const __p=new URLSearchParams(location.search);__p.set('bot_key',__token);__p.set('id',__dashboardTaskId);history.replaceState(null,'',location.pathname+'?'+__p.toString());
document.addEventListener('click',e=>{{if(e.target.closest('#back')){{e.preventDefault();e.stopImmediatePropagation();location.href='/tasks/'+encodeURIComponent(__token);}}}},true);
</script>"""
        html = html.replace('<script src="/static/task.js"></script>', bridge + '<script src="/static/task.js"></script>')
        _html(handler, 200, html)
        return True
    _json(handler, 404, {"error": "not_found"})
    return True

def handle_public_task_api(handler):
    path = urlparse(handler.path).path
    prefix = "/api/public-tasks/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix):].strip("/")
    parts = rest.split("/") if rest else []
    token = parts[0] if parts else ""
    if not token:
        _json(handler, 401, {"error": "unauthorized"})
        return True
    record = _auth(token)
    user_id, bot_key = str(record["user_id"]), str(record["bot_key"])

    # Older dashboard pages generated /api/public-tasks/{token}/bot_key={token}.
    # Treat that legacy suffix as compatibility metadata, not as a task id.
    if len(parts) == 2 and parts[1] == f"bot_key={token}":
        parts = [token]

    if len(parts) == 1 and handler.command == "GET":
        _json(handler, 200, {"tasks": handler.server.webapp_runtime.submit(list_tasks(user_id, bot_key))})
        return True
    if len(parts) == 1 and handler.command == "POST":
        data = _body(handler)
        title = str(data.get("title") or "").strip()
        if not title or len(title) > 500:
            _json(handler, 400, {"error": "invalid_title"})
            return True
        tid = handler.server.webapp_runtime.submit(create_task(user_id, bot_key, title=title, priority=str(data.get("priority") or "medium"), deadline=str(data.get("deadline") or ""), category=str(data.get("category") or ""), tags=data.get("tags") if isinstance(data.get("tags"), str) else ", ".join(map(str, data.get("tags") or [])), description=str(data.get("description") or ""), team_id=str(data.get("team_id") or "")))
        task = handler.server.webapp_runtime.submit(_full_task(user_id, tid, bot_key, handler.server.webapp_runtime))
        _json(handler, 201, {"task": task})
        return True
    if len(parts) == 2:
        task_id = parts[1]
        if handler.command == "GET":
            task = handler.server.webapp_runtime.submit(_full_task(user_id, task_id, bot_key, handler.server.webapp_runtime))
            _json(handler, 200, {"task": task}) if task else _json(handler, 404, {"error": "task_not_found"})
            return True
        if handler.command == "PATCH":
            data = _body(handler)
            task = handler.server.webapp_runtime.submit(get_task(user_id, task_id, bot_key))
            if not task:
                _json(handler, 404, {"error": "task_not_found"})
                return True
            if "status" in data:
                handler.server.webapp_runtime.submit(change_status(user_id, task_id, str(data["status"]), bot_key))
            allowed = {k: data[k] for k in ("title", "description", "priority", "deadline", "category", "tags") if k in data}
            if isinstance(allowed.get("tags"), list):
                allowed["tags"] = ", ".join(map(str, allowed["tags"]))
            if allowed:
                handler.server.webapp_runtime.submit(update_task(user_id, task_id, bot_key, **allowed))
            task = handler.server.webapp_runtime.submit(_full_task(user_id, task_id, bot_key, handler.server.webapp_runtime))
            _json(handler, 200, {"task": task})
            return True
    _json(handler, 404, {"error": "not_found"})
    return True
