# agent/tools/hooks_cta.py
"""generate_hooks_cta (этап 10): хуки и CTA к тексту поста.

LLM через call_llm(models.generation). Пишет hooks в state.
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


@tool
async def generate_hooks_cta(
    draft_text: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    user_id: Annotated[int, InjectedToolArg] = 0,
) -> dict:
    """Сгенерировать варианты хуков (цепляющих начал) и CTA для готового текста поста. Вызывать, когда текст уже есть и просят хуки/призыв к действию."""
    text = (draft_text or "").strip()
    if not text:
        logger.info("[hooks_cta.py] нет draft_text → error")
        return {"error": "Пока нет текста — сначала напишем пост, потом подберём хуки и CTA."}

    platform = (platform or "").strip() or "Telegram"

    try:
        prompt = render_prompt("generate_hooks_cta", draft_text=text, platform=platform)
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.8,
        )
        hooks = (result or "").strip()
        if not hooks:
            logger.info("[hooks_cta.py] пустой вывод LLM → error")
            return {"error": "Не удалось подобрать хуки, попробуй ещё раз."}

        logger.info("[hooks_cta.py] OK (len=%d)", len(hooks))
        return {
            "result": hooks,
            "updates_to_state": {"hooks": hooks, "cta_requested": True},
        }
    except Exception:
        logger.exception("[hooks_cta.py] failed")
        return {"error": "Техническая ошибка при генерации хуков и CTA."}