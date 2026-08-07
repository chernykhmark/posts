# db/repositories/posts.py

import json
from typing import Any, Optional

import asyncpg


class PostsRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create(
        self,
        user_id: int,
        text: str,
        platform: str,
        topic: Optional[str] = None,
        angle: Optional[str] = None,
        hooks_cta: Optional[Any] = None,
        hashtags: Optional[Any] = None,
        image_ref: Optional[str] = None,
    ) -> int:
        """Сохраняет финальный пост (БД = финал). Возвращает id.
        Мульти-платформа (TG+VK) = отдельный вызов create на каждую платформу (раздел 7)."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO posts
                    (user_id, topic, angle, text, hooks_cta, hashtags, image_ref, platform)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id,
                topic,
                angle,
                text,
                json.dumps(hooks_cta) if hooks_cta is not None else None,
                json.dumps(hashtags) if hashtags is not None else None,
                image_ref,
                platform,
            )

    async def get_last_n(self, user_id: int, n: int = 5) -> list[asyncpg.Record]:
        """Последние N постов для защиты от дублей (раздел 10, подмешивается в промпт)."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id, topic, angle, text, hooks_cta, hashtags, image_ref, platform, created_at
                FROM posts
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                n,
            )

    async def get_history(
        self, user_id: int, limit: int = 5, offset: int = 0
    ) -> list[asyncpg.Record]:
        """История с пагинацией (раздел 5). Возвращает поля для кратких карточек;
        обрезку текста до ~100 симв делает слой инструмента get_history, не БД."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT id, topic, platform, text, created_at
                FROM posts
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )