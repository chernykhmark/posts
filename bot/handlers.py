# bot/handlers.py
"""Хендлеры Telegram (дизайн-док, разделы 7, 7.1, 8).

Флоу обычного сообщения:
  get_or_create юзера
    → активный thread_id
    → thread-lock (queue/reject)
    → typing-loop
    → прогон графа
    → interrupt? (задел под этап 9) : ответ
  → stop typing (до ответа) + release lock (в finally)
"""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from agent import run_graph
from bot.thread_lock import ThreadBusy, thread_locks
from bot.thread_manager import get_or_create_thread, new_thread
from bot.typing import TypingIndicator
from db import get_db
from db.repositories import UsersRepo

logger = logging.getLogger(__name__)

router = Router(name="main")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await UsersRepo(get_db().pool).get_or_create(user_id=user.id, chat_id=message.chat.id)
    await message.answer(
        "Привет! Я помогу создать пост. Пришли тему — начнём.\n"
        "Команда /new — начать новый черновик с нуля."
    )


@router.message(Command("new"))
async def cmd_new(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await UsersRepo(get_db().pool).get_or_create(user_id=user.id, chat_id=message.chat.id)
    new_thread(user.id)  # старый черновик завершается (новый thread_id)
    await message.answer("Начал новый черновик. О чём будем писать?")


@router.message(F.text)
async def handle_text(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None or not message.text:
        return

    await UsersRepo(get_db().pool).get_or_create(user_id=user.id, chat_id=message.chat.id)
    thread_id = get_or_create_thread(user.id)

    # thread-lock: защита от конкурентных прогонов на одном thread.
    try:
        lock = await thread_locks.acquire(thread_id)
    except ThreadBusy:
        await message.answer("⏳ Агент ещё работает над прошлым запросом.")
        return

    typing = TypingIndicator(bot, message.chat.id)
    typing.start()
    try:
        result = await run_graph(
            thread_id=thread_id,
            user_message=message.text,
            user_id=user.id,
        )

        interrupt_payload = result.get("interrupt")
        reply = result.get("reply") or ""

        # typing снимаем до отправки ответа/вопроса (раздел 8).
        await typing.stop()

        if interrupt_payload is not None:
            # Задел под этап 9 (HITL). На эхо-графе сюда не попадаем.
            text = (
                interrupt_payload
                if isinstance(interrupt_payload, str)
                else str(interrupt_payload)
            )
            await message.answer(text)
        else:
            await message.answer(reply or "…")

    except Exception:
        logger.exception("graph run failed for thread=%s", thread_id)
        await typing.stop()
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз.")
    finally:
        await typing.stop()  # идемпотентно
        thread_locks.release(thread_id, lock)