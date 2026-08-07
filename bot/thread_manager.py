# bot/thread_manager.py
"""Хранение активного thread_id пользователя (дизайн-док, раздел 7, D-10).

MVP: in-memory dict {user_id: thread_id} на воркере.
При рестарте бота привязка теряется — приемлемо для MVP.
Колонка active_thread_id в users появится с v3.
"""
import uuid

_active_threads: dict[int, str] = {}


def get_or_create_thread(user_id: int) -> str:
    """Активный thread_id юзера или новый (первое сообщение)."""
    thread_id = _active_threads.get(user_id)
    if thread_id is None:
        thread_id = str(uuid.uuid4())
        _active_threads[user_id] = thread_id
    return thread_id


def new_thread(user_id: int) -> str:
    """/new — новый thread_id, старый черновик завершается."""
    thread_id = str(uuid.uuid4())
    _active_threads[user_id] = thread_id
    return thread_id