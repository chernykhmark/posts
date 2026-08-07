# agent/tools/generation.py
"""Инструменты генерации: make_angle, write_post, edit_post (этап 7).

Все три вызывают LLM через call_llm(models.generation) с промптами из prompts/.
Контекст из state прокидывается через InjectedToolArg (D-31, D-34).
Формат возврата — {result, updates_to_state} / {error} (D-12, Патч 4).

Инвариант: write_post != edit_post. write_post пишет с нуля,
edit_post вносит ТОЛЬКО запрошенное изменение (D-2, раздел 18).
"""

from typing import Annotated, Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import InjectedToolArg, tool

from config import settings
from agent.llm import call_llm
from agent.prompts import render_prompt
from db import get_db
from db.repositories import PostsRepo


def _format_rules_for(platform: str) -> str:
    """Правила форматирования платформы из config (D-15). Дефолт — Telegram."""
    rules = settings.format_rules.get(platform)
    if not rules:
        rules = settings.format_rules.get("Telegram", "")
    return rules


async def _recent_posts_block(user_id: int, platform: str) -> str:
    """Последние N постов автора для защиты от дублей (раздел 10)."""
    try:
        posts = await PostsRepo(get_db().pool).get_last_n(
            user_id, settings.recent_posts_limit
        )
    except Exception as e:
        print(f"[generation.py] get_last_n failed: {e}")
        return "(нет прошлых постов)"

    if not posts:
        return "(нет прошлых постов)"

    lines = []
    for p in posts:
        text = (p.get("text") or "").strip().replace("\n", " ")
        snippet = text[:150]
        lines.append(f"- {snippet}")
    return "\n".join(lines)


@tool
async def make_angle(
    topic: str,
    user_id: Annotated[int, InjectedToolArg] = 0,
) -> dict:
    """Придумать угол/ракурс подачи поста по теме. Вызывать, когда пользователь дал новую тему для поста, но угол ещё не выбран."""
    topic = (topic or "").strip()
    if not topic:
        print("[generation.py] make_angle: empty topic -> error")
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
            print("[generation.py] make_angle: empty LLM output -> error")
            return {"error": "Не удалось придумать угол, попробуй переформулировать тему."}

        print(f"[generation.py] make_angle OK: {angle[:80]!r}")
        return {
            "result": angle,
            "updates_to_state": {"topic": topic, "angle": angle},
        }
    except Exception as e:
        print(f"[generation.py] make_angle failed: {e}")
        return {"error": "Техническая ошибка при генерации угла."}


@tool
async def write_post(
    user_id: Annotated[int, InjectedToolArg] = 0,
    angle: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    style_description: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """Написать пост С НУЛЯ по выбранному углу, стилю автора и платформе. Вызывать для генерации нового текста поста (не для правки существующего)."""
    angle = (angle or "").strip()
    if not angle:
        print("[generation.py] write_post: no angle in state -> error")
        return {"error": "Сначала нужен угол поста — предложи или уточни угол."}

    platform = (platform or "").strip() or "Telegram"
    style_description = (style_description or "").strip() or "(стиль не задан)"

    try:
        recent = await _recent_posts_block(user_id, platform)
        prompt = render_prompt(
            "write_post",
            angle=angle,
            style_description=style_description,
            platform=platform,
            format_rules=_format_rules_for(platform),
            recent_posts=recent,
        )
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.9,
        )
        text = (result or "").strip()
        if not text:
            print("[generation.py] write_post: empty LLM output -> error")
            return {"error": "Не удалось сгенерировать текст, попробуй ещё раз."}

        print(f"[generation.py] write_post OK (platform={platform}, len={len(text)})")
        return {
            "result": text,
            "updates_to_state": {"draft_text": text, "platform": platform},
        }
    except Exception as e:
        print(f"[generation.py] write_post failed: {e}")
        return {"error": "Техническая ошибка при написании поста."}


@tool
async def edit_post(
    instruction: str,
    user_id: Annotated[int, InjectedToolArg] = 0,
    draft_text: Annotated[str, InjectedToolArg] = "",
    platform: Annotated[str, InjectedToolArg] = "",
    style_description: Annotated[str, InjectedToolArg] = "",
) -> dict:
    """Внести ТОЧЕЧНУЮ правку в существующий текст поста (например 'сделай короче', 'добавь эмодзи'). Меняет только запрошенное, остальное сохраняет. Вызывать для правки, НЕ для написания с нуля."""
    instruction = (instruction or "").strip()
    if not instruction:
        print("[generation.py] edit_post: empty instruction -> error")
        return {"error": "Не указано, что именно изменить."}

    draft_text = (draft_text or "").strip()
    if not draft_text:
        # сценарий А.3 №4: править нечего
        print("[generation.py] edit_post: no draft_text in state -> error")
        return {"error": "Пока нет текста для правки — сначала напишем пост."}

    platform = (platform or "").strip() or "Telegram"
    style_description = (style_description or "").strip() or "(стиль не задан)"

    try:
        prompt = render_prompt(
            "edit_post",
            draft_text=draft_text,
            instruction=instruction,
            style_description=style_description,
            platform=platform,
            format_rules=_format_rules_for(platform),
        )
        result = await call_llm(
            messages=[HumanMessage(content=prompt)],
            model=settings.models.generation,
            user_id=user_id,
            temperature=0.5,
        )
        text = (result or "").strip()
        if not text:
            print("[generation.py] edit_post: empty LLM output -> error")
            return {"error": "Не удалось применить правку, попробуй переформулировать."}

        print(f"[generation.py] edit_post OK (platform={platform}, len={len(text)})")
        return {
            "result": text,
            "updates_to_state": {"draft_text": text, "platform": platform},
        }
    except Exception as e:
        print(f"[generation.py] edit_post failed: {e}")
        return {"error": "Техническая ошибка при правке поста."}