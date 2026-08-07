# agent/checkpointer.py
"""Postgres checkpointer для LangGraph (память диалога, thread_id = черновик).

D-25: checkpointer LangGraph работает на psycopg3, поэтому держит СВОЙ
отдельный пул к той же БД. Прикладной слой (этап 2) остаётся на asyncpg.
Singleton на воркере (MVP = один воркер, аналогично D-22).
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from config import settings

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


def _psycopg_dsn() -> str:
    """DSN в формате psycopg3. settings.database_url собран под asyncpg,
    но строка postgresql://... совместима с обоими драйверами."""
    return settings.database_url


async def init_checkpointer() -> AsyncPostgresSaver:
    """Поднять пул psycopg + AsyncPostgresSaver, накатить его служебные таблицы.
    Идемпотентно: setup() создаёт таблицы IF NOT EXISTS."""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    _pool = AsyncConnectionPool(
        conninfo=_psycopg_dsn(),
        max_size=5,
        open=False,
        kwargs={"autocommit": True},
    )
    await _pool.open(wait=True)

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    logger.info("checkpointer initialized")
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer not initialized — call init_checkpointer() first")
    return _checkpointer


async def close_checkpointer() -> None:
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None
    logger.info("checkpointer closed")