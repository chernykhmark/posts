# bot/thread_lock.py
"""Thread-lock от конкурентных сообщений (дизайн-док, раздел 7.1, D-6).

Один прогон графа на thread_id одновременно — вопрос корректности
(гонка ломает checkpointer), а не фича.

Поведение из config:
  - concurrency_mode="queue"  — сообщения ждут, но не более queue_size
    в очереди на thread; лишние отклоняются.
  - concurrency_mode="reject" — пока thread занят, новые сразу отклоняются.
"""
import asyncio
import logging

from config import settings

logger = logging.getLogger(__name__)


class ThreadBusy(Exception):
    """Thread занят и место в очереди исчерпано / режим reject."""


class ThreadLockManager:
    """In-memory локи по thread_id (MVP = один воркер)."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiting: dict[str, int] = {}

    def _lock_for(self, thread_id: str) -> asyncio.Lock:
        lock = self._locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[thread_id] = lock
        return lock

    async def acquire(self, thread_id: str) -> asyncio.Lock:
        """Захватить lock на thread.

        Райзит ThreadBusy, если:
          - режим reject и thread занят;
          - режим queue и очередь переполнена (queue_size).
        Иначе (queue и есть место) — ждёт и возвращает захваченный lock.
        """
        lock = self._lock_for(thread_id)

        if not lock.locked():
            await lock.acquire()
            return lock

        mode = settings.concurrency_mode
        if mode == "reject":
            raise ThreadBusy()

        waiting = self._waiting.get(thread_id, 0)
        if waiting >= settings.queue_size:
            raise ThreadBusy()

        self._waiting[thread_id] = waiting + 1
        try:
            await lock.acquire()
        finally:
            self._waiting[thread_id] = self._waiting.get(thread_id, 1) - 1
        return lock

    def release(self, thread_id: str, lock: asyncio.Lock) -> None:
        """Освободить lock. Безопасно при повторном вызове."""
        if lock.locked():
            lock.release()
        if not lock.locked() and self._waiting.get(thread_id, 0) == 0:
            self._locks.pop(thread_id, None)
            self._waiting.pop(thread_id, None)


thread_locks = ThreadLockManager()