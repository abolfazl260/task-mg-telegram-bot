import pytest

from services import database


@pytest.fixture
async def test_db(monkeypatch):
    """Provide an isolated in-memory aiosqlite database for every test."""
    original_path = database.DB_PATH
    database.DB_PATH = ":memory:"

    # Database.connect currently expects a Path for production storage.
    # Patch the connection factory so the schema is still initialized in memory.
    import aiosqlite

    async def connect_memory(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(":memory:")
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys=ON")
        if not self.initialized:
            await self.conn.executescript(database.SCHEMA)
            await self.conn.commit()
            self.initialized = True
        return self.conn

    monkeypatch.setattr(database.Database, "connect", connect_memory)
    database._db_by_loop.clear()
    db = await database.get_db()
    yield db
    await database.close_db()
    database.DB_PATH = original_path
    database._db_by_loop.clear()


@pytest.fixture
def db_schema():
    return database.SCHEMA
