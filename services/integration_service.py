import csv
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime

from services.csv_manager import read_tasks, _write_all
from services.task_service import create_task

FILE_PATH = "data/integrations.csv"
HEADERS = [
    "user_id", "bot_key", "provider", "access_token", "refresh_token",
    "expires_at", "external_list_id", "external_list_name", "enabled", "last_sync"
]

MICROSOFT_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_GRAPH = "https://graph.microsoft.com/v1.0"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_TASKS = "https://tasks.googleapis.com/tasks/v1"

_pending_states = {}
_bots = {}


def init_integrations():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADERS)
        return
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    changed = False
    for row in rows:
        for h in HEADERS:
            if h not in row:
                row[h] = ""
                changed = True
    if changed:
        _write_integrations(rows)


def _read_integrations():
    init_integrations()
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_integrations(rows):
    with open(FILE_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in HEADERS})


def get_connection(user_id, provider, bot_key="default"):
    for row in _read_integrations():
        if row.get("user_id") == str(user_id) and row.get("provider") == provider and row.get("bot_key") == bot_key:
            return row
    return None


def connected(user_id, provider, bot_key="default"):
    row = get_connection(user_id, provider, bot_key)
    return bool(row and row.get("enabled") == "1" and row.get("refresh_token"))


def disconnect(user_id, provider, bot_key="default"):
    rows = _read_integrations()
    changed = False
    for row in rows:
        if row.get("user_id") == str(user_id) and row.get("provider") == provider and row.get("bot_key") == bot_key:
            row["enabled"] = "0"
            row["access_token"] = ""
            row["refresh_token"] = ""
            row["expires_at"] = ""
            changed = True
    if changed:
        _write_integrations(rows)
    return changed


def _redirect_uri(provider):
    base = os.getenv("INTEGRATION_REDIRECT_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("INTEGRATION_REDIRECT_BASE_URL تنظیم نشده است")
    return f"{base}/integrations/oauth/{provider}"


def start_oauth(provider, user_id, bot_key="default"):
    if provider not in ("microsoft", "google"):
        raise ValueError("ارائه‌دهنده نامعتبر است")
    state = secrets.token_urlsafe(32)
    _pending_states[state] = {"provider": provider, "user_id": str(user_id), "bot_key": bot_key, "created": time.time()}
    if provider == "microsoft":
        client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": _redirect_uri(provider),
            "response_mode": "query",
            "scope": "offline_access User.Read Tasks.ReadWrite",
            "state": state,
        }
        return MICROSOFT_AUTH + "?" + urllib.parse.urlencode(params)
    client_id = os.getenv("GOOGLE_TASKS_CLIENT_ID", "")
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": _redirect_uri(provider),
        "scope": "https://www.googleapis.com/auth/tasks",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return GOOGLE_AUTH + "?" + urllib.parse.urlencode(params)


def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def complete_oauth(provider, code, state):
    pending = _pending_states.pop(state, None)
    if not pending or pending["provider"] != provider or time.time() - pending["created"] > 600:
        raise ValueError("درخواست اتصال منقضی یا نامعتبر است")
    if provider == "microsoft":
        data = _post_form(MICROSOFT_TOKEN, {
            "client_id": os.getenv("MICROSOFT_CLIENT_ID", ""),
            "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", ""),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(provider),
            "scope": "offline_access User.Read Tasks.ReadWrite",
        })
    else:
        data = _post_form(GOOGLE_TOKEN, {
            "client_id": os.getenv("GOOGLE_TASKS_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_TASKS_CLIENT_SECRET", ""),
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(provider),
        })
    if "access_token" not in data:
        raise RuntimeError(data.get("error_description") or data.get("error") or "دریافت دسترسی ناموفق بود")
    expires_at = str(int(time.time()) + int(data.get("expires_in", 3600)) - 60)
    rows = _read_integrations()
    found = False
    for row in rows:
        if row.get("user_id") == pending["user_id"] and row.get("provider") == provider and row.get("bot_key") == pending["bot_key"]:
            row.update({"access_token": data["access_token"], "refresh_token": data.get("refresh_token") or row.get("refresh_token", ""), "expires_at": expires_at, "enabled": "1", "last_sync": ""})
            found = True
            break
    if not found:
        rows.append({
            "user_id": pending["user_id"], "bot_key": pending["bot_key"], "provider": provider,
            "access_token": data["access_token"], "refresh_token": data.get("refresh_token", ""),
            "expires_at": expires_at, "external_list_id": "", "external_list_name": "", "enabled": "1", "last_sync": ""
        })
    _write_integrations(rows)
    return pending


def register_bot(bot_key, bot):
    _bots[bot_key] = bot


def _refresh(row):
    if row.get("expires_at") and int(float(row["expires_at"])) > int(time.time()):
        return row.get("access_token")
    refresh = row.get("refresh_token")
    if not refresh:
        return row.get("access_token")
    if row["provider"] == "microsoft":
        data = _post_form(MICROSOFT_TOKEN, {
            "client_id": os.getenv("MICROSOFT_CLIENT_ID", ""),
            "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", ""),
            "grant_type": "refresh_token", "refresh_token": refresh,
            "scope": "offline_access User.Read Tasks.ReadWrite",
        })
    else:
        data = _post_form(GOOGLE_TOKEN, {
            "client_id": os.getenv("GOOGLE_TASKS_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_TASKS_CLIENT_SECRET", ""),
            "grant_type": "refresh_token", "refresh_token": refresh,
        })
    if "access_token" not in data:
        raise RuntimeError("تمدید دسترسی ناموفق بود")
    rows = _read_integrations()
    for item in rows:
        if item.get("user_id") == row.get("user_id") and item.get("provider") == row.get("provider") and item.get("bot_key") == row.get("bot_key"):
            item["access_token"] = data["access_token"]
            item["expires_at"] = str(int(time.time()) + int(data.get("expires_in", 3600)) - 60)
    _write_integrations(rows)
    row["access_token"] = data["access_token"]
    return row["access_token"]


def _request_json(url, token, method="GET", payload=None):
    body = None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"خطای سرویس {exc.code}: {detail[:300]}")


def _microsoft_lists(token):
    return _request_json(f"{MICROSOFT_GRAPH}/me/todo/lists", token).get("value", [])


def _google_lists(token):
    return _request_json(f"{GOOGLE_TASKS}/users/@me/lists?maxResults=100", token).get("items", [])


def get_lists(user_id, provider, bot_key="default"):
    row = get_connection(user_id, provider, bot_key)
    if not row:
        return []
    token = _refresh(row)
    return _microsoft_lists(token) if provider == "microsoft" else _google_lists(token)


def set_list(user_id, provider, list_id, list_name, bot_key="default"):
    rows = _read_integrations()
    for row in rows:
        if row.get("user_id") == str(user_id) and row.get("provider") == provider and row.get("bot_key") == bot_key:
            row["external_list_id"] = list_id
            row["external_list_name"] = list_name
            _write_integrations(rows)
            return True
    return False


def _ensure_list(row, lists):
    if row.get("external_list_id"):
        return row["external_list_id"]
    if not lists:
        raise RuntimeError("هیچ فهرستی در سرویس مقصد پیدا نشد")
    chosen = lists[0]
    list_id = chosen.get("id")
    list_name = chosen.get("displayName") or chosen.get("title") or ""
    set_list(row["user_id"], row["provider"], list_id, list_name, row["bot_key"])
    row["external_list_id"] = list_id
    return list_id


def _create_external(row, task):
    token = _refresh(row)
    provider = row["provider"]
    lists = _microsoft_lists(token) if provider == "microsoft" else _google_lists(token)
    list_id = _ensure_list(row, lists)
    description = (task.get("description") or "").strip()
    if provider == "microsoft":
        payload = {"title": task.get("title") or "بدون عنوان", "body": {"content": description, "contentType": "text"}}
        if task.get("deadline"):
            payload["dueDateTime"] = {"dateTime": _deadline_iso(task["deadline"]), "timeZone": "UTC"}
        return _request_json(f"{MICROSOFT_GRAPH}/me/todo/lists/{urllib.parse.quote(list_id, safe='')}/tasks", token, "POST", payload)
    payload = {"title": task.get("title") or "بدون عنوان"}
    if description:
        payload["notes"] = description
    if task.get("deadline"):
        payload["due"] = _deadline_iso(task["deadline"], google=True)
    return _request_json(f"{GOOGLE_TASKS}/lists/{urllib.parse.quote(list_id, safe='')}/tasks", token, "POST", payload)


def _deadline_iso(value, google=False):
    try:
        dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except Exception:
        try:
            dt = datetime.strptime(value.strip(), "%Y-%m-%d")
        except Exception:
            return value
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if google else dt.strftime("%Y-%m-%dT%H:%M:%S")


def _is_done(item, provider):
    return (item.get("status") == "completed") if provider == "microsoft" else (item.get("status") == "completed")


def sync_user(user_id, bot_key="default", provider=None):
    providers = [provider] if provider else ["microsoft", "google"]
    results = []
    for name in providers:
        row = get_connection(user_id, name, bot_key)
        if not row or row.get("enabled") != "1":
            continue
        try:
            token = _refresh(row)
            lists = _microsoft_lists(token) if name == "microsoft" else _google_lists(token)
            list_id = _ensure_list(row, lists)
            if name == "microsoft":
                external = _request_json(f"{MICROSOFT_GRAPH}/me/todo/lists/{urllib.parse.quote(list_id, safe='')}/tasks?$top=100", token).get("value", [])
            else:
                external = _request_json(f"{GOOGLE_TASKS}/lists/{urllib.parse.quote(list_id, safe='')}/tasks?maxResults=100", token).get("items", [])
            tasks = read_tasks()
            local_by_id = {t.get("id"): t for t in tasks}
            external_by_marker = {}
            for item in external:
                notes = item.get("body", {}).get("content", "") if name == "microsoft" else item.get("notes", "")
                marker = "[BOT_TASK:" in notes
                if marker:
                    try:
                        local_id = notes.split("[BOT_TASK:", 1)[1].split("]", 1)[0]
                        external_by_marker[local_id] = item
                    except Exception:
                        pass
            changed = 0
            for task in tasks:
                if str(task.get("user_id")) != str(user_id):
                    continue
                ext = external_by_marker.get(task.get("id"))
                if not ext:
                    ext = _create_external(row, task)
                    if name == "microsoft":
                        body = ext.get("body", {}).get("content", "")
                        ext_id = ext.get("id")
                        update_payload = {"body": {"content": f"[BOT_TASK:{task.get('id')}]\n{body}", "contentType": "text"}}
                        _request_json(f"{MICROSOFT_GRAPH}/me/todo/lists/{urllib.parse.quote(list_id, safe='')}/tasks/{urllib.parse.quote(ext_id, safe='')}", token, "PATCH", update_payload)
                    else:
                        ext_id = ext.get("id")
                        update_payload = {"notes": f"[BOT_TASK:{task.get('id')}]\n{task.get('description') or ''}"}
                        _request_json(f"{GOOGLE_TASKS}/lists/{urllib.parse.quote(list_id, safe='')}/tasks/{urllib.parse.quote(ext_id, safe='')}", token, "PATCH", update_payload)
                    changed += 1
                    continue
                if _is_done(ext, name) and task.get("status") != "done":
                    task["status"] = "done"
                    task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    changed += 1
                elif not _is_done(ext, name) and task.get("status") == "done":
                    task["status"] = "pending"
                    task["completed_at"] = ""
                    changed += 1
            _write_all(tasks)
            rows = _read_integrations()
            for item in rows:
                if item.get("user_id") == str(user_id) and item.get("provider") == name and item.get("bot_key") == bot_key:
                    item["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _write_integrations(rows)
            results.append((name, changed, None))
        except Exception as exc:
            results.append((name, 0, str(exc)))
    return results


def sync_all(bot_key="default"):
    users = sorted({r.get("user_id") for r in _read_integrations() if r.get("bot_key") == bot_key and r.get("enabled") == "1"})
    return [(uid, sync_user(uid, bot_key)) for uid in users]
