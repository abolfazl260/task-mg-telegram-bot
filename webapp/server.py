"""HTTP server for the Telegram Web App and admin dashboard."""
from __future__ import annotations

import logging
import sqlite3
import asyncio, json, mimetypes, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse, unquote
from .config import WEBAPP_HOST, WEBAPP_PORT
from .api import authenticate_telegram_request
from .auth import TelegramWebAppAuthError
from .bot_profile import WebAppBotProfileError, get_webapp_bot_profile
from .tasks_api import WebAppTaskAccessError, get_task, list_tasks, list_work_item_types, create_task, update_task, change_status
from .public_tasks import handle_public_task_get, handle_public_task_api
from .database_explorer import database_explorer_rows, database_explorer_tables
from .admin_api import (
    activate_bot_management,
    bot_feature_registry,
    bot_management,
    bot_management_audit,
    create_bot_management,
    dashboard_stats,
    deactivate_bot_management,
    get_bot_management_detail,
    get_user_profile,
    list_user_tasks,
    list_users,
    system_health,
    task_creation,
    task_status_distribution,
    update_bot_management,
    validate_bot_management_token,
)
from services.healthcare.access import ClinicAccessError
from .clinic_api import dispatch as clinic_dispatch

logger = logging.getLogger(__name__)
ADMIN_PATH = "/backoffice"
STATIC_DIR = Path(__file__).resolve().parent / "static"
class WebAppAsyncRuntime:
    def __init__(self): self.loop=asyncio.new_event_loop(); self.thread=Thread(target=self._run,name="telegram-webapp-async",daemon=True)
    def _run(self): asyncio.set_event_loop(self.loop); self.loop.run_forever()
    def start(self): self.thread.start()
    def submit(self,coroutine): return asyncio.run_coroutine_threadsafe(coroutine,self.loop).result()
    def stop(self):
        if self.loop.is_closed(): return
        self.loop.call_soon_threadsafe(self.loop.stop); self.thread.join(timeout=5)
        if not self.loop.is_closed(): self.loop.close()
def _json_body(handler):
    length=int(handler.headers.get("Content-Length","0") or 0)
    if length>64*1024: raise ValueError("request_too_large")
    data=json.loads((handler.rfile.read(length) if length else b"{}").decode("utf-8"))
    if not isinstance(data,dict): raise ValueError("invalid_json")
    return data
class WebAppHandler(BaseHTTPRequestHandler):
    def _json(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False,default=str).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def _bot_key(self): return (parse_qs(urlparse(self.path).query).get("bot_key") or [""])[0].strip()
    def _authenticate(self,bot_key): return authenticate_telegram_request(self.headers.get("X-Telegram-Init-Data",""),bot_key)
    def _serve_static(self,path):
        relative=path.removeprefix("/static/") if path.startswith("/static/") else ""
        if path=="/": relative="index.html"
        if path in {"/clinic-report", "/clinic-report/"}: relative="clinic-report.html"
        if path in {ADMIN_PATH, ADMIN_PATH+"/"}: relative="admin/index.html"
        if not relative or ".." in Path(relative).parts: return False
        target=(STATIC_DIR/relative).resolve()
        if STATIC_DIR not in target.parents and target!=STATIC_DIR or not target.is_file(): return False
        body=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(target.name)[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return True
    def _authenticate_admin(self):
        from services.admin_access import resolve_admin_token
        cookies = parse_qs(self.headers.get("Cookie", "").replace(";", "&"))
        token = unquote(cookies.get("admin_session", [""])[0])
        if not token:
            # Keep the token-bearing backoffice URL usable when a browser or
            # embedded webview blocks third-party/session cookies.
            referer = urlparse(self.headers.get("Referer", "")).path
            if referer.startswith(ADMIN_PATH + "/"):
                token = unquote(referer[len(ADMIN_PATH) + 1:].strip("/"))
        admin_id = resolve_admin_token(token)
        # The token was issued by /backoffice only after an admin check. The
        # short-lived, hashed token is the session credential for API calls;
        # re-checking a separately loaded ADMIN_IDS list here can reject a
        # valid session after configuration reload.
        if not admin_id:
            raise WebAppTaskAccessError("admin_required")
        return type("Admin", (), {"id": int(admin_id)})()

    def _handle_admin(self,method):
        path=urlparse(self.path).path
        query=parse_qs(urlparse(self.path).query)
        bot_key=(query.get("bot_key") or [""])[0].strip()
        admin=self._authenticate_admin()

        if path=="/api/admin/dashboard" and method=="GET":
            return self._json(200,self.server.webapp_runtime.submit(dashboard_stats(bot_key)))
        if path=="/api/admin/tasks/status" and method=="GET":
            return self._json(200,{"statuses":self.server.webapp_runtime.submit(task_status_distribution(bot_key))})
        if path=="/api/admin/bots" and method=="GET":
            return self._json(200,{"bots":self.server.webapp_runtime.submit(bot_management())})
        if path=="/api/admin/bot-features" and method=="GET":
            return self._json(200,self.server.webapp_runtime.submit(bot_feature_registry()))
        if path=="/api/admin/bots/validate-token" and method=="POST":
            return self._json(200,self.server.webapp_runtime.submit(validate_bot_management_token(_json_body(self))))
        if path=="/api/admin/bots" and method=="POST":
            return self._json(201,{"bot":self.server.webapp_runtime.submit(create_bot_management(_json_body(self),admin.id))})
        if path.startswith("/api/admin/bots/"):
            remainder=path[len("/api/admin/bots/"):].strip("/")
            if remainder.endswith("/activate") and method=="POST":
                key=remainder[:-9].rstrip("/")
                if not key: return self._json(400,{"error":"invalid_bot_key"})
                return self._json(200,{"bot":self.server.webapp_runtime.submit(activate_bot_management(key,admin.id))})
            if remainder.endswith("/deactivate") and method=="POST":
                key=remainder[:-11].rstrip("/")
                if not key: return self._json(400,{"error":"invalid_bot_key"})
                return self._json(200,{"bot":self.server.webapp_runtime.submit(deactivate_bot_management(key,admin.id))})
            if remainder.endswith("/audit") and method=="GET":
                key=remainder[:-6].rstrip("/")
                if not key: return self._json(400,{"error":"invalid_bot_key"})
                return self._json(200,{"events":self.server.webapp_runtime.submit(bot_management_audit(key))})
            key=remainder
            if not key: return self._json(400,{"error":"invalid_bot_key"})
            if method=="GET":
                bot=self.server.webapp_runtime.submit(get_bot_management_detail(key))
                return self._json(200,{"bot":bot}) if bot else self._json(404,{"error":"bot_not_found"})
            if method=="PATCH":
                return self._json(200,{"bot":self.server.webapp_runtime.submit(update_bot_management(key,_json_body(self),admin.id))})
            return self._json(405,{"error":"method_not_allowed"})
        if path=="/api/admin/system-health" and method=="GET":
            return self._json(200,self.server.webapp_runtime.submit(system_health()))
        if path=="/api/admin/database/tables" and method=="GET":
            return self._json(200,self.server.webapp_runtime.submit(database_explorer_tables()))
        if path=="/api/admin/database/rows" and method=="GET":
            table=(query.get("table") or [""])[0].strip()
            try:
                limit=int((query.get("limit") or ["50"])[0])
                offset=int((query.get("offset") or ["0"])[0])
            except ValueError:
                return self._json(400,{"error":"invalid_pagination"})
            try:
                filters=json.loads((query.get("filters") or ["[]"])[0] or "[]")
            except json.JSONDecodeError:
                return self._json(400,{"error":"invalid_filters"})
            try:
                payload=self.server.webapp_runtime.submit(database_explorer_rows(
                    table,
                    filters=filters,
                    sort=(query.get("sort") or [""])[0].strip(),
                    direction=(query.get("direction") or [""])[0].strip(),
                    limit=limit,
                    offset=offset,
                ))
            except TypeError as exc:
                return self._json(400,{"error":str(exc)})
            return self._json(200,payload)
        if path=="/api/admin/tasks/creation" and method=="GET":
            try: days=int((query.get("days") or ["7"])[0])
            except ValueError: return self._json(400,{"error":"invalid_days"})
            if days not in (7,30): return self._json(400,{"error":"days_must_be_7_or_30"})
            return self._json(200,self.server.webapp_runtime.submit(task_creation(days,bot_key)))
        if path=="/api/admin/users" and method=="GET":
            try: limit=int((query.get("limit") or ["50"])[0]); offset=int((query.get("offset") or ["0"])[0])
            except ValueError: return self._json(400,{"error":"invalid_pagination"})
            return self._json(200,self.server.webapp_runtime.submit(list_users(bot_key,(query.get("search") or [""])[0],limit,offset)))
        if path.startswith("/api/admin/users/") and method=="GET":
            remainder=path[len("/api/admin/users/"):]
            if remainder.endswith("/tasks"):
                user_id=remainder[:-6].rstrip("/")
                if not user_id: return self._json(400,{"error":"invalid_user_id"})
                return self._json(200,{"tasks":self.server.webapp_runtime.submit(list_user_tasks(user_id,bot_key))})
            user_id=remainder.strip("/")
            if not user_id: return self._json(400,{"error":"invalid_user_id"})
            profile=self.server.webapp_runtime.submit(get_user_profile(user_id,bot_key))
            return self._json(200,{"user":profile}) if profile else self._json(404,{"error":"user_not_found"})
        if path.startswith("/api/admin/"):
            return self._json(405,{"error":"method_not_allowed"}) if method not in {"GET","POST","PATCH"} else self._json(404,{"error":"not_found"})
        return self._json(404,{"error":"not_found"})

    def _handle_api(self,method):
        path=urlparse(self.path).path; bot_key=self._bot_key()
        known = path.startswith(("/api/clinic/", "/api/tasks/")) or path in {"/api/me", "/api/tasks"}
        if not known:
            return self._json(404,{"error":"not_found"})
        profile=get_webapp_bot_profile(bot_key)
        if (path=="/api/tasks" or path.startswith("/api/tasks/")) and not profile.feature_enabled("tasks"):
            raise WebAppTaskAccessError("tasks_feature_disabled")
        if path.startswith("/api/clinic/") and not profile.feature_enabled("healthcare"):
            raise WebAppTaskAccessError("healthcare_feature_disabled")
        user=self._authenticate(bot_key)
        if path.startswith("/api/clinic/"):
            data=_json_body(self) if method in {"POST","PATCH"} else {}
            status,payload=self.server.webapp_runtime.submit(clinic_dispatch(user.id,bot_key,method,path,parse_qs(urlparse(self.path).query),data))
            return self._json(status,payload)
        if path=="/api/me" and method=="GET":
            return self._json(200,{"user":user.__dict__,"bot_key":bot_key,"work_item_types":self.server.webapp_runtime.submit(list_work_item_types(bot_key))})
        if path=="/api/tasks" and method=="GET":
            if not profile.permission_enabled("tasks.view"):
                raise WebAppTaskAccessError("tasks_view_permission_denied")
            work_item_type=(parse_qs(urlparse(self.path).query).get("work_item_type") or [None])[0]
            return self._json(200,{"tasks":self.server.webapp_runtime.submit(list_tasks(user.id,bot_key,work_item_type=work_item_type))})
        if path=="/api/tasks" and method=="POST":
            if not profile.permission_enabled("tasks.create"):
                raise WebAppTaskAccessError("tasks_create_permission_denied")
            data=_json_body(self); title=str(data.get("title") or "").strip()
            if not title or len(title)>500: return self._json(400,{"error":"invalid_title"})
            feature_fields={"priority":"priority","deadline":"deadline","category":"categories","tags":"tags"}
            field_permissions={"priority":"priority.set","deadline":"deadline.set","category":"categories.manage","tags":"tags.manage"}
            for field,feature in feature_fields.items():
                if field in data and data.get(field) not in (None,"",[]):
                    if not profile.feature_enabled(feature):
                        raise WebAppTaskAccessError(f"{feature}_feature_disabled")
                    if not profile.permission_enabled(field_permissions[field]):
                        raise WebAppTaskAccessError(f"{field_permissions[field].replace('.','_')}_permission_denied")
            if data.get("team_id") and not profile.permission_enabled("assignment.manage"):
                raise WebAppTaskAccessError("assignment_manage_permission_denied")
            tid=self.server.webapp_runtime.submit(create_task(user.id,bot_key,title=title,priority=str(data.get("priority") or "medium"),deadline=str(data.get("deadline") or ""),category=str(data.get("category") or ""),tags=data.get("tags") if isinstance(data.get("tags"),str) else ", ".join(map(str,data.get("tags") or [])),description=str(data.get("description") or ""),team_id=str(data.get("team_id") or ""),work_item_type=data.get("work_item_type")))
            return self._json(201,{"task":self.server.webapp_runtime.submit(get_task(user.id,tid,bot_key))})
        if path.startswith("/api/tasks/"):
            task_id=path.rsplit("/",1)[-1]
            if not task_id: return self._json(400,{"error":"invalid_task_id"})
            if method=="GET":
                if not profile.permission_enabled("tasks.view"):
                    raise WebAppTaskAccessError("tasks_view_permission_denied")
                task=self.server.webapp_runtime.submit(get_task(user.id,task_id,bot_key)); return self._json(200,{"task":task}) if task else self._json(404,{"error":"task_not_found"})
            if method=="PATCH":
                data=_json_body(self)
                if not profile.permission_enabled("tasks.update"):
                    raise WebAppTaskAccessError("tasks_update_permission_denied")
                task=self.server.webapp_runtime.submit(get_task(user.id,task_id,bot_key))
                if not task: return self._json(404,{"error":"task_not_found"})
                if "status" in data:
                    if not profile.permission_enabled("tasks.status"):
                        raise WebAppTaskAccessError("tasks_status_permission_denied")
                    self.server.webapp_runtime.submit(change_status(user.id,task_id,str(data["status"]),bot_key))
                feature_fields={"priority":"priority","deadline":"deadline","category":"categories","tags":"tags"}
                field_permissions={"priority":"priority.set","deadline":"deadline.set","category":"categories.manage","tags":"tags.manage"}
                for field,feature in feature_fields.items():
                    if field in data:
                        if not profile.feature_enabled(feature):
                            raise WebAppTaskAccessError(f"{feature}_feature_disabled")
                        if not profile.permission_enabled(field_permissions[field]):
                            raise WebAppTaskAccessError(f"{field_permissions[field].replace('.','_')}_permission_denied")
                allowed={k:data[k] for k in ("title","description","priority","deadline","category","tags") if k in data}
                if "tags" in allowed and isinstance(allowed["tags"],list): allowed["tags"]=", ".join(map(str,allowed["tags"]))
                if allowed: self.server.webapp_runtime.submit(update_task(user.id,task_id,bot_key,**allowed))
                return self._json(200,{"task":self.server.webapp_runtime.submit(get_task(user.id,task_id,bot_key))})
        return self._json(404,{"error":"not_found"})
    def _dispatch(self,method):
        try:
            path=urlparse(self.path).path
            if path.startswith("/api/public-tasks/"):
                return handle_public_task_api(self)
            return self._handle_admin(method) if path.startswith("/api/admin/") else self._handle_api(method)
        except TelegramWebAppAuthError: return self._json(401,{"error":"unauthorized"})
        except WebAppBotProfileError: return self._json(400,{"error":"invalid_bot_profile"})
        except (WebAppTaskAccessError,ClinicAccessError): return self._json(403,{"error":"forbidden"})
        except sqlite3.IntegrityError: return self._json(409,{"error":"conflict"})
        except ValueError as e: return self._json(400,{"error":"invalid_request" if urlparse(self.path).path.startswith("/api/clinic/") else str(e)})
        except Exception:
            if urlparse(self.path).path.startswith("/api/clinic/"):
                logger.error("clinic_request_failed method=%s",method)
            else:
                logger.exception("webapp_task_request_failed method=%s path=%s operation=task_api", method, self.path)
            return self._json(500,{"error":"internal_server_error"})
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith(ADMIN_PATH + "/") and path != ADMIN_PATH + "/":
            from services.admin_access import resolve_admin_token
            token = unquote(path[len(ADMIN_PATH)+1:].strip("/"))
            if resolve_admin_token(token):
                # Keep the expiring token in the address bar. This avoids a
                # redirect to a cookie-only URL, which breaks in strict or
                # embedded browsers.
                self.send_response(200)
                body = (STATIC_DIR / "admin/index.html").read_bytes()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Set-Cookie", f"admin_session={token}; Max-Age=600; HttpOnly; SameSite=Lax; Path=/")
                self.end_headers(); self.wfile.write(body)
            else:
                self._json(404,{"error":"expired_or_invalid_admin_link"})
            return
        if path.startswith("/tasks/") or path.startswith("/task/"):
            return handle_public_task_get(self)
        if path in {"/","/static/index.html",ADMIN_PATH,ADMIN_PATH+"/"} or path.startswith("/static/"): return self._serve_static(path) or self._json(404,{"error":"not_found"})
        if path in {"/health","/healthz"}: return self._json(200,{"status":"ok","service":"telegram-webapp"})
        return self._dispatch("GET")
    def do_POST(self): return self._dispatch("POST")
    def do_PATCH(self): return self._dispatch("PATCH")
    def do_OPTIONS(self): self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Content-Type, X-Telegram-Init-Data"); self.send_header("Access-Control-Allow-Methods","GET, POST, PATCH, OPTIONS"); self.end_headers()
    def log_message(self,format,*args): return
class WebAppHTTPServer(ThreadingHTTPServer): webapp_runtime: WebAppAsyncRuntime
def create_server():
    host=os.getenv("WEBAPP_HOST", WEBAPP_HOST)
    port=int(os.getenv("WEBAPP_PORT", str(WEBAPP_PORT)))
    server=WebAppHTTPServer((host,port),WebAppHandler); server.webapp_runtime=WebAppAsyncRuntime(); server.webapp_runtime.start(); return server
def run():
    server=create_server(); print(f"Telegram Web App server listening on {WEBAPP_HOST}:{WEBAPP_PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.shutdown(); server.webapp_runtime.stop(); server.server_close()
if __name__=="__main__": run()
