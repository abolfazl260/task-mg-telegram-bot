"""HTTP server for the Telegram Web App foundation and task API."""
from __future__ import annotations
import asyncio, json, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse
from .api import authenticate_telegram_request
from .auth import TelegramWebAppAuthError
from .bot_profile import WebAppBotProfileError
from .config import WEBAPP_HOST, WEBAPP_PORT
from .tasks_api import WebAppTaskAccessError, get_task, list_tasks, create_task, update_task, change_status
STATIC_DIR = Path(__file__).resolve().parent / "static"

class WebAppAsyncRuntime:
    def __init__(self):
        self.loop=asyncio.new_event_loop(); self.thread=Thread(target=self._run,name="telegram-webapp-async",daemon=True)
    def _run(self): asyncio.set_event_loop(self.loop); self.loop.run_forever()
    def start(self): self.thread.start()
    def submit(self, coroutine): return asyncio.run_coroutine_threadsafe(coroutine,self.loop).result()
    def stop(self):
        if self.loop.is_closed(): return
        self.loop.call_soon_threadsafe(self.loop.stop); self.thread.join(timeout=5)
        if not self.loop.is_closed(): self.loop.close()

def _json_body(handler):
    length=int(handler.headers.get("Content-Length","0") or 0)
    if length > 64*1024: raise ValueError("request_too_large")
    raw=handler.rfile.read(length) if length else b"{}"
    data=json.loads(raw.decode("utf-8"))
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
        if not relative or ".." in Path(relative).parts: return False
        target=(STATIC_DIR/relative).resolve()
        if STATIC_DIR not in target.parents and target!=STATIC_DIR or not target.is_file(): return False
        body=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(target.name)[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return True
    def _handle_api(self,method):
        parsed=urlparse(self.path); path=parsed.path; bot_key=self._bot_key(); user=self._authenticate(bot_key)
        if path=="/api/me" and method=="GET": return self._json(200,{"user":user.__dict__,"bot_key":bot_key})
        if path=="/api/tasks" and method=="GET": return self._json(200,{"tasks":self.server.webapp_runtime.submit(list_tasks(user.id,bot_key))})
        if path=="/api/tasks" and method=="POST":
            data=_json_body(self); title=str(data.get("title") or "").strip()
            if not title or len(title)>500: return self._json(400,{"error":"invalid_title"})
            tid=self.server.webapp_runtime.submit(create_task(user.id,bot_key,title=title,priority=str(data.get("priority") or "medium"),deadline=str(data.get("deadline") or ""),category=str(data.get("category") or ""),tags=data.get("tags") if isinstance(data.get("tags"),str) else ", ".join(data.get("tags") or []),description=str(data.get("description") or ""),team_id=str(data.get("team_id") or ""))
            task=self.server.webapp_runtime.submit(get_task(user.id,tid,bot_key))
            return self._json(201,{"task":task})
        if path.startswith("/api/tasks/"):
            task_id=path.rsplit("/",1)[-1]
            if not task_id: return self._json(400,{"error":"invalid_task_id"})
            if method=="GET":
                task=self.server.webapp_runtime.submit(get_task(user.id,task_id,bot_key))
                return self._json(200,{"task":task}) if task else self._json(404,{"error":"task_not_found"})
            if method=="PATCH":
                data=_json_body(self)
                if "status" in data:
                    ok=self.server.webapp_runtime.submit(change_status(user.id,task_id,str(data["status"]),bot_key))
                else:
                    allowed={k:data[k] for k in ("title","description","priority","deadline","category","tags") if k in data}
                    if "tags" in allowed and isinstance(allowed["tags"],list): allowed["tags"]=", ".join(str(x) for x in allowed["tags"])
                    ok=self.server.webapp_runtime.submit(update_task(user.id,task_id,bot_key,**allowed))
                if not ok: return self._json(404,{"error":"task_not_found_or_forbidden"})
                return self._json(200,{"task":self.server.webapp_runtime.submit(get_task(user.id,task_id,bot_key))})
        return self._json(404,{"error":"not_found"})
    def do_GET(self):
        path=urlparse(self.path).path
        if path in {"/","/static/index.html"} or path.startswith("/static/"):
            return self._serve_static(path) or self._json(404,{"error":"not_found"})
        if path in {"/health","/healthz"}: return self._json(200,{"status":"ok","service":"telegram-webapp"})
        try: return self._handle_api("GET")
        except TelegramWebAppAuthError: return self._json(401,{"error":"unauthorized"})
        except WebAppBotProfileError: return self._json(400,{"error":"invalid_bot_profile"})
        except WebAppTaskAccessError: return self._json(403,{"error":"forbidden"})
        except ValueError as e: return self._json(400,{"error":str(e)})
        except Exception: return self._json(500,{"error":"internal_server_error"})
    def do_POST(self):
        try: return self._handle_api("POST")
        except TelegramWebAppAuthError: return self._json(401,{"error":"unauthorized"})
        except WebAppBotProfileError: return self._json(400,{"error":"invalid_bot_profile"})
        except WebAppTaskAccessError: return self._json(403,{"error":"forbidden"})
        except ValueError as e: return self._json(400,{"error":str(e)})
        except Exception: return self._json(500,{"error":"internal_server_error"})
    def do_PATCH(self):
        try: return self._handle_api("PATCH")
        except TelegramWebAppAuthError: return self._json(401,{"error":"unauthorized"})
        except WebAppBotProfileError: return self._json(400,{"error":"invalid_bot_profile"})
        except WebAppTaskAccessError: return self._json(403,{"error":"forbidden"})
        except ValueError as e: return self._json(400,{"error":str(e)})
        except Exception: return self._json(500,{"error":"internal_server_error"})
    def do_OPTIONS(self): self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Content-Type, X-Telegram-Init-Data"); self.send_header("Access-Control-Allow-Methods","GET, POST, PATCH, OPTIONS"); self.end_headers()
    def log_message(self,format,*args): return

class WebAppHTTPServer(ThreadingHTTPServer): webapp_runtime: WebAppAsyncRuntime

def create_server():
    server=WebAppHTTPServer((WEBAPP_HOST,WEBAPP_PORT),WebAppHandler); server.webapp_runtime=WebAppAsyncRuntime(); server.webapp_runtime.start(); return server

def run():
    server=create_server(); print(f"Telegram Web App server listening on {WEBAPP_HOST}:{WEBAPP_PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.shutdown(); server.webapp_runtime.stop(); server.server_close()

if __name__=="__main__": run()
