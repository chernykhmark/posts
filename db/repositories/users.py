# db/repositories/users.py

from typing import Optional

import asyncpg


class UsersRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_or_create(self, user_id: int, chat_id: int) -> asyncpg.Record:
        """Возвращает пользователя, создавая при первом обращении.
        chat_id обновляется на случай смены чата."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (user_id, chat_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET chat_id = EXCLUDED.chat_id
                RETURNING user_id, chat_id, auto_mode, created_at
                """,
                user_id,
                chat_id,
            )
            return row

    async def get_auto_mode(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            val = await conn.fetchval(
                "SELECT auto_mode FROM users WHERE user_id = $1",
                user_id,
            )
            return bool(val) if val is not None else False

    async def set_auto_mode(self, user_id: int, auto_mode: bool) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET auto_mode = $2 WHERE user_id = $1",
                user_id,
                auto_mode,
            )