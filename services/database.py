from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from typing import Any, Iterable
import aiosqlite

DB_PATH = Path('data/data.db')
SCHEMA = '''
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;
CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,full_name TEXT NOT NULL DEFAULT '',username TEXT NOT NULL DEFAULT '',timezone TEXT NOT NULL DEFAULT 'UTC',date_format TEXT NOT NULL DEFAULT 'jalali',first_seen TEXT NOT NULL DEFAULT '',last_seen TEXT NOT NULL DEFAULT '',messages_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS teams(team_id TEXT PRIMARY KEY,name TEXT NOT NULL,owner_id TEXT NOT NULL REFERENCES users(user_id),editor_code TEXT NOT NULL UNIQUE,viewer_code TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS team_members(team_id TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,role TEXT NOT NULL,display_name TEXT NOT NULL DEFAULT '',username TEXT NOT NULL DEFAULT '',joined_at TEXT NOT NULL DEFAULT '',PRIMARY KEY(team_id,user_id));
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,bot_key TEXT NOT NULL DEFAULT 'default',user_id TEXT NOT NULL REFERENCES users(user_id),title TEXT NOT NULL,priority TEXT NOT NULL DEFAULT 'medium',status TEXT NOT NULL DEFAULT 'pending',deadline TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT '',tags TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT '',completed_at TEXT NOT NULL DEFAULT '',team_id TEXT REFERENCES teams(team_id) ON DELETE SET NULL,assignee_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,assignee_name TEXT NOT NULL DEFAULT '',assignee_username TEXT NOT NULL DEFAULT '',jira_key TEXT NOT NULL DEFAULT '',jira_sync_hash TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS task_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,author_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,author_name TEXT NOT NULL DEFAULT '',author_username TEXT NOT NULL DEFAULT '',content_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS task_assignment_history(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,actor_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,action TEXT NOT NULL DEFAULT '',old_assignee_name TEXT NOT NULL DEFAULT '',new_assignee_name TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS habits(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,title TEXT NOT NULL,category TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',repeat_type TEXT NOT NULL DEFAULT 'daily',target TEXT NOT NULL DEFAULT '',reminder_time TEXT NOT NULL DEFAULT '',start_date TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS habit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,done_date TEXT NOT NULL,done_at TEXT NOT NULL DEFAULT '',UNIQUE(habit_id,user_id,done_date));
CREATE TABLE IF NOT EXISTS jira_connections(bot_key TEXT NOT NULL,user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,base_url TEXT NOT NULL,identity TEXT NOT NULL DEFAULT '',credential TEXT NOT NULL DEFAULT '',project_key TEXT NOT NULL,deployment TEXT NOT NULL DEFAULT 'cloud',issue_type TEXT NOT NULL DEFAULT 'Task',account_id TEXT NOT NULL DEFAULT '',auth_method TEXT NOT NULL DEFAULT 'basic',connected_at TEXT NOT NULL DEFAULT '',last_sync_at TEXT NOT NULL DEFAULT '',PRIMARY KEY(bot_key,user_id));
CREATE TABLE IF NOT EXISTS jira_task_links(bot_key TEXT NOT NULL,task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,jira_key TEXT NOT NULL,sync_hash TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT '',PRIMARY KEY(bot_key,task_id),UNIQUE(bot_key,jira_key));
CREATE TABLE IF NOT EXISTS custom_bots(bot_key TEXT PRIMARY KEY,owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,owner_name TEXT NOT NULL DEFAULT '',owner_username TEXT NOT NULL DEFAULT '',bot_token TEXT NOT NULL DEFAULT '',bot_username TEXT NOT NULL DEFAULT '',features TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'active',pricing_plan TEXT NOT NULL DEFAULT 'free_beta',created_at TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS business_connections(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,user_chat_id TEXT NOT NULL DEFAULT '',username TEXT NOT NULL DEFAULT '',full_name TEXT NOT NULL DEFAULT '',date TEXT NOT NULL DEFAULT '',can_reply INTEGER NOT NULL DEFAULT 0,is_enabled INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS business_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,business_connection_id TEXT REFERENCES business_connections(id) ON DELETE CASCADE,chat_id TEXT NOT NULL DEFAULT '',message_id TEXT NOT NULL DEFAULT '',from_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,from_username TEXT NOT NULL DEFAULT '',text TEXT NOT NULL DEFAULT '',message_ids_json TEXT NOT NULL DEFAULT '[]',date TEXT NOT NULL DEFAULT '',recorded_at TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_bot_key ON tasks(bot_key);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_comments_task_id ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignment_task_id ON task_assignment_history(task_id);
CREATE INDEX IF NOT EXISTS idx_members_user_id ON team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_id);
CREATE INDEX IF NOT EXISTS idx_habit_logs_user_date ON habit_logs(user_id,done_date);
CREATE INDEX IF NOT EXISTS idx_jira_links_key ON jira_task_links(jira_key);
CREATE INDEX IF NOT EXISTS idx_business_messages_connection ON business_messages(business_connection_id);
'''

async def init_db():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def fetch_all(table:str,where:str='',params:Iterable[Any]=()):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute(f'SELECT * FROM {table}'+(f' WHERE {where}' if where else ''),tuple(params)) as cur:
            return [dict(x) for x in await cur.fetchall()]

async def fetch_one(table,where,params=()):
    rows=await fetch_all(table,where,params); return rows[0] if rows else None

async def execute(sql,params=()):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('PRAGMA foreign_keys=ON'); cur=await db.execute(sql,tuple(params)); await db.commit(); return cur.lastrowid

async def transaction(statements):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('PRAGMA foreign_keys=ON'); await db.execute('BEGIN IMMEDIATE')
        try:
            for sql,params in statements: await db.execute(sql,tuple(params))
            await db.commit()
        except Exception: await db.rollback(); raise

def _run(coro):
    try: asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(coro)
    result=[]; errors=[]
    def worker():
        try: result.append(asyncio.run(coro))
        except BaseException as e: errors.append(e)
    t=threading.Thread(target=worker,daemon=True); t.start(); t.join()
    if errors: raise errors[0]
    return result[0] if result else None

def sync_all(table,where='',params=()): return _run(fetch_all(table,where,params))
def sync_one(table,where,params=()): return _run(fetch_one(table,where,params))
def sync_execute(sql,params=()): return _run(execute(sql,params))
def sync_transaction(statements): return _run(transaction(statements))
