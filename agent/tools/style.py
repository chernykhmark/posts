# agent/tools/style.py
"""
analyze_style (этап 6) — заменяет заглушку.
draft → models.cheap по промпту prompts/analyze_style.md → style_description
→ upsert в style_profiles (по user_id).
"""
import logging
from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool

from agent.llm import call_llm
from agent.prompts import render_prompt
from config import settings
from db import get_db
from db.repositories import StyleProfilesRepo

logger = logging.getLogger(__name__)


@tool
async def analyze_style(
    draft: str,
    user_id: Annotated[int | None, InjectedToolArg] = None,
) -> dict:
    """Проанализировать стиль пользователя из присланного черновика-примера
    и сохранить описание стиля."""
    logger.info("[style.py] analyze_style ENTER: draft_len=%s user_id=%r",
                len(draft or ""), user_id)

    if not draft or not draft.strip():
        logger.warning("[style.py] draft is empty")
        return {"error": "draft is empty: нужен текст-образец для анализа стиля"}

    if user_id is None:
        logger.error("[style.py] user_id NOT injected! (проверь tool_node)")
        return {"error": "user_id missing for analyze_style"}

    try:
        prompt = render_prompt("analyze_style", draft=draft)
        style_description = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.cheap,
            user_id=user_id,
            temperature=0.3,
        )
        logger.info("[style.py] call_llm OK: style_len=%s",
                    len(style_description or ""))
    except Exception as e:
        logger.exception("[style.py] analyze_style LLM failed: %s", e)
        return {"error": f"analyze_style failed: {e}"}

    if not style_description:
        logger.error("[style.py] empty LLM response")
        return {"error": "analyze_style: пустой ответ модели"}

    try:
        repo = StyleProfilesRepo(get_db().pool)
        await repo.upsert(user_id=user_id, style_description=style_description)
        logger.info("[style.py] upsert OK for user_id=%s", user_id)
    except Exception as e:
        logger.exception("[style.py] style_profiles upsert FAILED: %s", e)
        return {"error": f"failed to save style: {e}"}

    return {
        "result": "Стиль проанализирован и сохранён.",
        "updates_to_state": {"style_description": style_description},
    }