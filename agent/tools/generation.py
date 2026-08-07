# agent/tools/generation.py
"""Инструменты генерации: make_angle, write_post, edit_post (этап 7).

Все три вызывают LLM через call_llm(models.generation) с промптами из prompts/.
Контекст из state прокидывается через InjectedToolArg (D-31, D-34).
Формат возврата — {result, updates_to_state} / {error} (D-12, Патч 4).

Инвариант: write_post != edit_post. write_post пишет с нуля,
edit_post вносит ТОЛЬКО запрошенное изменение (D-2, раздел 18).
"""
import logging
from typing import Annotated

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool

from config import settings
from agent.llm import call_llm
from agent.prompts import render_prompt
from db import get_db
from db.repositories import PostsRepo

logger = logging.getLogger(__name__)


def _format_rules_for(platform: str) -> str:
    """Правила форматирования платформы из config (D-15). Дефолт — Telegram."""
    rules = settings.format_rules.get(platform)
    if not rules:
        rules = settings.format_rules.get("Telegram", "")
    return rules


async def _recent_posts_list(user_id: int) -> list[str]:
    """Последние N постов автора (тексты) для защиты от дублей (раздел 10)."""
    try:
        rows = await PostsRepo(get_db().pool).get_last_n(
            user_id, settings.recent_posts_limit
        )
    except Exception:
        logger.exception("[generation.py] get_last_n недоступен")
        return []
    return [(r.get("text") or "").strip() for r in rows if r.get("text")]


@tool
async def make_angle(
    topic: str,
    user_id: Annotated[int, InjectedToolArg] = 0,
) -> dict:
    """Придумать угол/ракурс подачи поста по теме. Вызывать, когда пользователь дал новую тему для поста, но угол ещё не выбран."""
    topic = (topic or "").strip()
    if not topic:
        logger.info("[generation.py] make_angle: пустая тема → error")
        return {"error": "Не указана тема для угла."}

    try:
        prompt = render_prompt("make_angle", topic=topic)
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.8,
        )
        angle = (result or "").strip()
        if not angle:
            logger.info("[generation.py] make_angle: пустой вывод LLM → error")
            return {"error": "Не удалось придумать угол, попробуй переформулировать тему."}

        logger.info("[generation.py] make_angle OK: %r", angle[:80])
        return {
            "result": angle,
            "updates_to_state": {"topic": topic, "angle": angle},
        }
    except Exception:
        logger.exception("[generation.py] make_angle failed")
        return {"error": "Техническая ошибка при генерации угла."}


@tool
async def write_post(
    angle: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    style_description: Annotated[str, InjectedToolArg] = "",
    user_id: Annotated[int, InjectedToolArg] = 0,
    critique_issues: Annotated[list, InjectedToolArg] = None,
) -> dict:
    """Написать пост С НУЛЯ по выбранному углу, стилю автора и платформе. Вызывать для генерации нового текста поста (не для правки существующего)."""
    angle = (angle or "").strip()
    if not angle:
        logger.info("[generation.py] write_post: пустой angle → error")
        return {"error": "Сначала нужен угол поста — предложи или уточни угол."}

    platform = (platform or "").strip() or "Telegram"
    style_description = (style_description or "").strip() or "(стиль не задан)"

    try:
        recent_posts = await _recent_posts_list(user_id)

        issues_block = ""
        if critique_issues:
            issues_block = (
                "Обязательно исправь проблемы предыдущей версии:\n- "
                + "\n- ".join(critique_issues)
            )

        prompt = render_prompt(
            "write_post",
            angle=angle,
            platform=platform,
            format_rules=_format_rules_for(platform),
            style_description=style_description,
            recent_posts="\n---\n".join(recent_posts) if recent_posts else "нет",
            critique_issues=issues_block,
        )
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.9,
        )
        text = (result or "").strip()
        if not text:
            logger.info("[generation.py] write_post: пустой вывод LLM → error")
            return {"error": "Не удалось сгенерировать текст, попробуй ещё раз."}

        logger.info("[generation.py] write_post OK (platform=%s, len=%d)", platform, len(text))
        return {
            "result": text,
            "updates_to_state": {"draft_text": text, "platform": platform},
        }
    except Exception:
        logger.exception("[generation.py] write_post failed")
        return {"error": "Техническая ошибка при написании поста."}


@tool
async def edit_post(
    instruction: str,
    draft_text: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    style_description: Annotated[str, InjectedToolArg] = "",
    user_id: Annotated[int, InjectedToolArg] = 0,
    critique_issues: Annotated[list, InjectedToolArg] = None,
) -> dict:
    """Внести ТОЧЕЧНУЮ правку в существующий текст поста (например 'сделай короче', 'добавь эмодзи'). Меняет только запрошенное, остальное сохраняет. Вызывать для правки, НЕ для написания с нуля."""
    draft_text = (draft_text or "").strip()
    if not draft_text:
        # сценарий А.3 №4: править нечего
        logger.info("[generation.py] edit_post: нет draft_text → error")
        return {"error": "Пока нет текста для правки — сначала напишем пост."}

    platform = (platform or "").strip() or "Telegram"
    style_description = (style_description or "").strip() or "(стиль не задан)"

    # если правка инициирована critique — инструкция берётся из issues
    if critique_issues:
        instruction = "Исправь проблемы:\n- " + "\n- ".join(critique_issues)
    instruction = (instruction or "").strip()
    if not instruction:
        logger.info("[generation.py] edit_post: пустая instruction → error")
        return {"error": "Не указано, что именно изменить."}

    try:
        prompt = render_prompt(
            "edit_post",
            draft_text=draft_text,
            instruction=instruction,
            platform=platform,
            format_rules=_format_rules_for(platform),
            style_description=style_description,
        )
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.5,
        )
        text = (result or "").strip()
        if not text:
            logger.info("[generation.py] edit_post: пустой вывод LLM → error")
            return {"error": "Не удалось применить правку, попробуй переформулировать."}

        logger.info("[generation.py] edit_post OK (platform=%s, len=%d)", platform, len(text))
        return {
            "result": text,
            "updates_to_state": {"draft_text": text, "platform": platform},
        }
    except Exception:
        logger.exception("[generation.py] edit_post failed")
        return {"error": "Техническая ошибка при правке поста."}