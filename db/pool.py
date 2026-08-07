# db/pool.py

import logging
from pathlib import Path
from typing import Optional

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """Тонкая обертка над asyncpg-пулом + применение SQL-миграции."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def create(cls, dsn: str) -> "Database":
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        db = cls(pool)
        await db.apply_migrations()
        return db

    async def apply_migrations(self) -> None:
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(sql)
        logger.info("db migrations applied")

    async def close(self) -> None:
        await self.pool.close()
        logger.info("db pool closed")


# Глобальный singleton пула (MVP, один воркер).
_db: Optional[Database] = None


async def init_db() -> Database:
    global _db
    if _db is None:
        _db = await Database.create(settings.database_url)
        logger.info("db initialized")
    return _db


def get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None