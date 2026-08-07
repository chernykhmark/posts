# agent/critique.py
"""Critique-цикл (этап 8): code-проверки (без LLM) + LLM-оценка стиля.

Контракт (раздел 4.3):
  Вход: text, platform, angle, style_description, recent_posts.
  Выход: {verdict, issues, checks, failed_count}
    checks = {length, markup, cta, angle_match}
    verdict="ok" ⇔ issues пустой И все code-проверки прошли.
Единый источник правил — FORMAT_RULES + чек-лист А.2.
"""
from __future__ import annotations

import json
import logging
import re

from config import settings
from agent.llm import call_llm
from agent.prompts import render_prompt

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "это", "как", "что", "для", "или", "тоже", "если", "быть", "есть", "были",
    "твой", "ваш", "наш", "они", "она", "оно", "мой", "который", "которая",
    "чтобы", "потому", "когда", "тогда", "здесь", "туда", "сюда", "очень",
    "теперь", "просто", "можно", "нужно", "надо", "будет", "будут", "весь",
    "все", "всех", "этот", "эта", "этих", "того", "тому", "чем", "уже",
    "with", "that", "this", "your", "from", "have", "will", "about", "into",
}

_MD_MARKERS = ("*", "_", "`", "[", "]")


def _platform_max_len(platform: str) -> int | None:
    rules = settings.format_rules.get(platform, "")
    m = re.search(r"(\d[\d\s]{2,})\s*симв", rules)
    if not m:
        return None
    try:
        return int(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def check_length(text: str, platform: str) -> bool:
    max_len = _platform_max_len(platform)
    if max_len is None:
        return True
    return len(text) <= int(max_len * 1.15)


def check_markup(text: str, platform: str) -> bool:
    if platform.lower() == "vk":
        return not any(marker in text for marker in _MD_MARKERS)
    for marker in ("*", "_"):
        if text.count(marker) % 2 != 0:
            return False
    return True


def check_cta(text: str, cta_requested: bool) -> bool:
    if not cta_requested:
        return True
    lowered = text.lower()
    if "http" in lowered or "@" in text or "?" in text:
        return True
    cta_markers = (
        "подпис", "переход", "жми", "кликай", "оставь", "пиши", "напиши",
        "заходи", "регистр", "успей", "забирай", "получи", "узнай",
        "ставь", "делись", "сохрани", "комментир",
    )
    return any(m in lowered for m in cta_markers)


def _keywords(angle: str) -> list[str]:
    words = re.findall(r"[а-яА-ЯёЁa-zA-Z]{5,}", angle.lower())
    return [w for w in words if w not in _STOPWORDS]


def check_angle_match(text: str, angle: str) -> bool:
    keys = _keywords(angle)
    if not keys:
        return True
    lowered = text.lower()
    hits = sum(1 for k in keys if k[:5] in lowered)
    return (hits / len(keys)) >= 0.30


def run_code_checks(text: str, platform: str, angle: str, cta_requested: bool) -> dict:
    return {
        "length": check_length(text, platform),
        "markup": check_markup(text, platform),
        "cta": check_cta(text, cta_requested),
        "angle_match": check_angle_match(text, angle),
    }


def code_issues(checks: dict, platform: str) -> list[str]:
    issues: list[str] = []
    if not checks["length"]:
        issues.append(f"Текст превышает лимит длины для платформы {platform}.")
    if not checks["markup"]:
        if platform.lower() == "vk":
            issues.append("Для VK убери всю Markdown-разметку — только чистый текст.")
        else:
            issues.append("Сломанная Markdown-разметка (непарные * или _).")
    if not checks["cta"]:
        issues.append("Отсутствует запрошенный призыв к действию (CTA).")
    if not checks["angle_match"]:
        issues.append("Текст слабо соответствует заданному углу — усиль связь с темой.")
    return issues


def _parse_llm_issues(raw: str) -> list[str]:
    if not raw:
        return []
    txt = raw.strip()
    start = txt.find("{")
    end = txt.rfind("}")
    if start != -1 and end != -1 and end > start:
        txt = txt[start : end + 1]
    try:
        data = json.loads(txt)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[critique.py] LLM-оценка: не распарсил JSON, считаю ok. raw=%r", raw[:200])
        return []
    issues = data.get("issues") or []
    if isinstance(issues, str):
        issues = [issues]
    return [str(i).strip() for i in issues if str(i).strip()]


async def llm_style_check(
    user_id: int,
    text: str,
    platform: str,
    style_description: str,
    recent_posts: list[str],
) -> list[str]:
    recent = "\n---\n".join(recent_posts) if recent_posts else "нет"
    prompt = render_prompt(
        "critique",
        text=text,
        platform=platform,
        format_rules=settings.format_rules.get(platform, ""),
        style_description=style_description or "стиль не задан",
        recent_posts=recent,
    )
    raw = await call_llm(
        model=settings.models.critique,
        messages=[HumanMessage(content=prompt)],
        user_id=user_id,
        temperature=0.2,
    )
    return _parse_llm_issues(raw)


async def critique_text(
    *,
    user_id: int,
    text: str,
    platform: str,
    angle: str,
    style_description: str,
    recent_posts: list[str],
    cta_requested: bool,
) -> dict:
    checks = run_code_checks(text, platform, angle, cta_requested)
    issues = code_issues(checks, platform)
    failed_count = sum(1 for v in checks.values() if not v)

    if issues:
        logger.info("[critique.py] code-checks FAILED: %s", checks)
        return {"verdict": "revise", "issues": issues, "checks": checks, "failed_count": failed_count}

    style_issues = await llm_style_check(
        user_id=user_id,
        text=text,
        platform=platform,
        style_description=style_description,
        recent_posts=recent_posts,
    )
    if style_issues:
        logger.info("[critique.py] code OK, LLM issues: %s", style_issues)
        return {"verdict": "revise", "issues": style_issues, "checks": checks, "failed_count": 0}

    logger.info("[critique.py] verdict=ok")
    return {"verdict": "ok", "issues": [], "checks": checks, "failed_count": 0}