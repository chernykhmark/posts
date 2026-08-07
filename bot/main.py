# bot/main.py
"""Entrypoint Telegram-бота.

Этап 4: при старте поднимаем пул БД (asyncpg) + миграции,
затем Postgres checkpointer (psycopg3) и компилируем граф.
Сообщения проходят через граф (bot/handlers.py) с typing и thread-lock.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from agent import build_graph, close_checkpointer, init_checkpointer
from bot.handlers import router
from config import settings
from db import close_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # 1. Прикладной слой БД (asyncpg) + миграции
    await init_db()
    logger.info("db migrations applied")

    # 2. Checkpointer LangGraph (psycopg3) + компиляция графа
    await init_checkpointer()
    build_graph()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await close_checkpointer()
        await close_db()
        logger.info("bot stopped")


if __name__ == "__main__":
    asyncio.run(main())