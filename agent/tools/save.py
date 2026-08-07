# agent/tools/save.py
"""save_post (этап 10): сохранить текущий готовый пост в историю (БД = финал).

БЕЗ LLM. state → posts. Нет draft_text → {error} (сценарий А.3 №7).
Флаг saved защищает от повторного сохранения без изменений (D-40).
Мультиплатформа: если в state есть несколько вариантов — несколько записей;
на MVP генерируется один вариант, потому обычно одна запись (D-40).
Формат возврата — {result, updates_to_state} / {error} (D-12).
"""
import logging
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from db import get_db
from db.repositories import PostsRepo

logger = logging.getLogger(__name__)


@tool
async def save_post(
    user_id: Annotated[int, InjectedToolArg] = 0,
    topic: Annotated[str, InjectedToolArg] = "",
    angle: Annotated[str, InjectedToolArg] = "",
    draft_text: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    hooks: Annotated[object, InjectedToolArg] = None,
    hashtags: Annotated[object, InjectedToolArg] = None,
    saved: Annotated[bool, InjectedToolArg] = False,
    saved_post_ids: Annotated[list, InjectedToolArg] = None,
) -> dict:
    """Сохранить текущий готовый пост в историю. Вызывать, когда пользователь просит сохранить пост и текст уже готов."""
    text = (draft_text or "").strip()
    if not text:
        # сценарий А.3 №7: сохранять нечего
        logger.info("[save.py] нет draft_text → error")
        return {"error": "Пока нечего сохранять — сначала подготовим текст поста."}

    if saved:
        logger.info("[save.py] пост уже сохранён (ids=%s)", saved_post_ids)
        return {
            "result": "Этот пост уже сохранён. Если внесём правки — сможем сохранить обновлённую версию.",
            "updates_to_state": {},
        }

    platform_value = (platform or "").strip() or "Telegram"
    # мультиплатформа-задел (D-40): поддержка списка платформ, если появится
    platforms = [p.strip() for p in platform_value.split(",") if p.strip()] or ["Telegram"]

    try:
        repo = PostsRepo(get_db().pool)
        new_ids = []
        for p in platforms:
            post_id = await repo.create(
                user_id=user_id,
                text=text,
                platform=p,
                topic=topic or None,
                angle=angle or None,
                hooks_cta=hooks,
                hashtags=hashtags,
            )
            new_ids.append(post_id)
    except Exception:
        logger.exception("[save.py] create failed")
        return {"error": "Техническая ошибка при сохранении поста."}

    logger.info("[save.py] OK (ids=%s, platforms=%s)", new_ids, platforms)
    word = "запись" if len(new_ids) == 1 else "записи"
    return {
        "result": f"Пост сохранён ✅ ({len(new_ids)} {word}, id: {', '.join(map(str, new_ids))}).",
        "updates_to_state": {"saved": True, "saved_post_ids": new_ids},
    }