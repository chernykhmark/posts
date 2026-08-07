# db/repositories/usage_costs.py

from decimal import Decimal
from typing import Union

import asyncpg


class UsageCostsRepo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def log_cost(
        self,
        user_id: int,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost: Union[float, Decimal],
    ) -> None:
        """Пишется ПОСЛЕ КАЖДОГО LLM-вызова (D-8, раздел 13). Без лимитов — это v3."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO usage_costs (user_id, model, tokens_in, tokens_out, cost)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                model,
                tokens_in,
                tokens_out,
                Decimal(str(cost)),
            )