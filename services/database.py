from __future__ import annotations
import atexit, asyncio, sqlite3
from pathlib import Path
import aiosqlite
DB_PATH=Path('data/data.db')
SCHEMA="PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=10000;"
class Database:
    def __init__(self): self.conn=None; self.lock=asyncio.Lock(); self.initialized=False
    async def connect(self):
        if self.conn is None:
            DB_PATH.parent.mkdir(parents=True,exist_ok=True); self.conn=await aiosqlite.connect(DB_PATH); self.conn.row_factory=aiosqlite.Row
            await self.conn.execute('PRAGMA foreign_keys=ON'); await self.conn.execute('PRAGMA busy_timeout=10000'); await self.conn.execute('PRAGMA journal_mode=WAL'); await self.conn.execute('PRAGMA synchronous=NORMAL')
        if not self.initialized: await self.conn.executescript(SCHEMA); await self.conn.commit(); self.initialized=True
        return self.conn
    async def close(self):
        if self.conn is not None: await self.conn.close(); self.conn=None; self.initialized=False
_db_by_loop={}
async def get_db():
    k=id(asyncio.get_running_loop()); db=_db_by_loop.get(k)
    if db is None: db=Database(); _db_by_loop[k]=db
    await db.connect(); return db
async def init_db(): await get_db()
async def close_db():
    k=id(asyncio.get_running_loop()); db=_db_by_loop.pop(k,None)
    if db: await db.close()
async def fetch_all(table,where='',params=()):
    db=await get_db(); q=f'SELECT * FROM {table}'+(f' WHERE {where}' if where else '')
    async with db.conn.execute(q,tuple(params)) as cur: return [dict(r) for r in await cur.fetchall()]
async def fetch_one(table,where,params=()):
    rows=await fetch_all(table,where,params); return rows[0] if rows else None
async def execute(sql,params=()):
    db=await get_db()
    async with db.lock:
        cur=await db.conn.execute(sql,tuple(params)); await db.conn.commit(); return cur.lastrowid
async def execute_many(sql,rows):
    db=await get_db()
    async with db.lock: await db.conn.executemany(sql,[tuple(r) for r in rows]); await db.conn.commit()
async def transaction(statements):
    db=await get_db()
    async with db.lock:
        await db.conn.execute('BEGIN IMMEDIATE')
        try:
            for sql,p in statements: await db.conn.execute(sql,tuple(p))
            await db.conn.commit()
        except Exception: await db.conn.rollback(); raise

def _run(coro):
    # Sync compatibility helper. It must not call asyncio.run() from an active loop.
    try: asyncio.get_running_loop()
    except RuntimeError: return asyncio.run(coro)
    raise RuntimeError('Synchronous database helper called from an active event loop; use the async database API instead.')

def _sync_sql(sql,params=(),fetch='none'):
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    try:
        cur=conn.execute(sql,tuple(params))
        if fetch=='one': out=cur.fetchone(); result=dict(out) if out else None
        elif fetch=='all': result=[dict(r) for r in cur.fetchall()]
        else: result=cur.lastrowid
        conn.commit(); return result
    finally: conn.close()
def sync_all(table,where='',params=()): return _sync_sql(f'SELECT * FROM {table}'+(f' WHERE {where}' if where else ''),params,'all')
def sync_one(table,where,params=()): return _sync_sql(f'SELECT * FROM {table} WHERE {where}',params,'one')
def sync_execute(sql,params=()): return _sync_sql(sql,params,'none')
def sync_transaction(statements):
    conn=sqlite3.connect(DB_PATH)
    try:
        conn.execute('BEGIN IMMEDIATE')
        for sql,p in statements: conn.execute(sql,tuple(p))
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()
def get_connection(): return sqlite3.connect(DB_PATH)
def close_all(): _db_by_loop.clear()
atexit.register(close_all)
