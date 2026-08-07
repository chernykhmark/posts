# agent/tools/stubs.py
"""Инструменты-заглушки (этап 5). Реальная логика — на своих этапах.

Осталось 4 заглушки: generate_hooks_cta, generate_hashtags,
get_history, save_post (этап 10).
Реальные: analyze_style (этап 6), make_angle/write_post/edit_post (этап 7).
Формат возврата — {result, updates_to_state} (D-12).
"""

from langchain_core.tools import tool


@tool
async def generate_hooks_cta(text: str) -> dict:
    """Сгенерировать варианты хуков (цепляющих начал) и CTA для поста."""
    return {"result": "stub:generate_hooks_cta", "updates_to_state": {}}


@tool
async def generate_hashtags(text: str) -> dict:
    """Подобрать хэштеги к посту."""
    return {"result": "stub:generate_hashtags", "updates_to_state": {}}


@tool
async def get_history(limit: int = 5, offset: int = 0) -> dict:
    """Показать прошлые сохранённые посты пользователя (с пагинацией)."""
    return {"result": "stub:get_history", "updates_to_state": {}}


@tool
async def save_post() -> dict:
    """Сохранить текущий готовый пост в историю."""
    return {"result": "stub:save_post", "updates_to_state": {}}