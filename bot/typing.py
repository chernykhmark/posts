# bot/typing.py
"""Typing-индикатор (дизайн-док, раздел 8, D-5).

Циклический sendChatAction(typing) каждые typing_interval сек, пока
агент работает. Telegram гасит индикатор ~5 сек — шлём повторно.
Снимается на ответе и на interrupt (через stop()).
"""
import asyncio
import contextlib
import logging

from aiogram import Bot
from aiogram.enums import ChatAction

from config import settings

logger = logging.getLogger(__name__)


class TypingIndicator:
    """Управляет фоновым typing-loop. start() / stop() идемпотентны."""

    def __init__(self, bot: Bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        try:
            while True:
                try:
                    await self._bot.send_chat_action(
                        chat_id=self._chat_id, action=ChatAction.TYPING
                    )
                except Exception as e:  # индикатор не должен ронять прогон
                    logger.warning("typing send_chat_action failed: %s", e)
                await asyncio.sleep(settings.typing_interval)
        except asyncio.CancelledError:
            pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None