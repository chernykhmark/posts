# agent/tools/hashtags.py
"""generate_hashtags (этап 10): хэштеги к тексту поста.

LLM через call_llm(models.cheap). Пишет hashtags в state.
Формат возврата — {result, updates_to_state} / {error} (D-12, D-36).
"""
import logging
from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool

from config import settings
from agent.llm import call_llm
from agent.prompts import render_prompt

logger = logging.getLogger(__name__)


def _parse_hashtags(raw: str) -> list[str]:
    """Достаёт #теги из ответа LLM; при отсутствии решётки — режет по строкам/пробелам."""
    tokens = raw.replace(",", " ").split()
    tags = [t.strip().rstrip(".") for t in tokens if t.strip().startswith("#")]
    if not tags:
        # LLM могла вернуть слова без решётки — нормализуем
        tags = ["#" + t.strip().lstrip("#") for t in raw.split() if t.strip()]
    # уникализируем, сохраняя порядок
    seen, out = set(), []
    for t in tags:
        low = t.lower()
        if low not in seen:
            seen.add(low)
            out.append(t)
    return out[:15]


@tool
async def generate_hashtags(
    draft_text: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    user_id: Annotated[int, InjectedToolArg] = 0,
) -> dict:
    """Подобрать релевантные хэштеги к готовому тексту поста. Вызывать, когда текст уже есть и просят хэштеги."""
    text = (draft_text or "").strip()
    if not text:
        logger.info("[hashtags.py] нет draft_text → error")
        return {"error": "Пока нет текста — сначала напишем пост, потом подберём хэштеги."}

    platform = (platform or "").strip() or "Telegram"

    try:
        prompt = render_prompt("generate_hashtags", draft_text=text, platform=platform)
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.cheap,
            user_id=user_id,
            temperature=0.5,
        )
        tags = _parse_hashtags((result or "").strip())
        if not tags:
            logger.info("[hashtags.py] пустой вывод LLM → error")
            return {"error": "Не удалось подобрать хэштеги, попробуй ещё раз."}

        logger.info("[hashtags.py] OK (%d тегов)", len(tags))
        return {
            "result": " ".join(tags),
            "updates_to_state": {"hashtags": tags},
        }
    except Exception:
        logger.exception("[hashtags.py] failed")
        return {"error": "Техническая ошибка при подборе хэштегов."}