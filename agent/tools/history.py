# agent/tools/history.py
"""get_history (этап 10): прошлые сохранённые посты пользователя.

БЕЗ LLM. Пагинация limit/offset, краткие карточки (не полные тексты, раздел 5).
Формат возврата — {result, updates_to_state} / {error} (D-12).
"""
import logging
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from db import get_db
from db.repositories import PostsRepo

logger = logging.getLogger(__name__)

_SNIPPET_LEN = 100


def _card(row) -> str:
    topic = (row.get("topic") or "").strip() or "без темы"
    platform = (row.get("platform") or "").strip() or "?"
    text = (row.get("text") or "").strip().replace("\n", " ")
    snippet = text[:_SNIPPET_LEN] + ("…" if len(text) > _SNIPPET_LEN else "")
    created = row.get("created_at")
    date = created.strftime("%Y-%m-%d %H:%M") if created else "?"
    return f"#{row.get('id')} · {platform} · {date}\n{topic}: {snippet}"


@tool
async def get_history(
    limit: int = 5,
    offset: int = 0,
    user_id: Annotated[int, InjectedToolArg] = 0,
) -> dict:
    """Показать прошлые сохранённые посты пользователя (краткие карточки, с пагинацией). Вызывать, когда просят показать историю/прошлые посты."""
    limit = max(1, min(int(limit or 5), 20))
    offset = max(0, int(offset or 0))

    try:
        rows = await PostsRepo(get_db().pool).get_history(user_id, limit, offset)
    except Exception:
        logger.exception("[history.py] get_history недоступен")
        return {"error": "Не удалось получить историю постов."}

    if not rows:
        logger.info("[history.py] пусто (offset=%d)", offset)
        return {
            "result": "История пуста." if offset == 0 else "Больше сохранённых постов нет.",
            "updates_to_state": {},
        }

    cards = "\n\n".join(_card(dict(r)) for r in rows)
    logger.info("[history.py] OK (%d карточек, offset=%d)", len(rows), offset)
    return {"result": cards, "updates_to_state": {}}