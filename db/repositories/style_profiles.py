# db/repositories/style_profiles.py

from typing import Optional

import asyncpg


class StyleProfilesRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get(self, user_id: int) -> Optional[str]:
        """Возвращает style_description или None, если стиля еще нет (ветка 4.2)."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT style_description FROM style_profiles WHERE user_id = $1",
                user_id,
            )

    async def upsert(self, user_id: int, style_description: str) -> None:
        """Создает или переписывает стиль (при новом черновике — переанализ, раздел 9)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO style_profiles (user_id, style_description, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (user_id)
                DO UPDATE SET style_description = EXCLUDED.style_description,
                             updated_at = now()
                """,
                user_id,
                style_description,
            )