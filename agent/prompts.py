# agent/prompts.py
"""
Загрузчик промптов из каталога prompts/ (по файлу на инструмент, структура А.1).
Промпты УНИВЕРСАЛЬНЫ: ниша подставляется через переменные
(style_description, angle, platform, последние N постов и т.п.).

Подстановка переменных — безопасная: отсутствующие плейсхолдеры не роняют вызов,
а заменяются на пустую строку (важно для опциональных полей вроде style_description).
"""
import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_cache: dict[str, str] = {}


class _SafeDict(dict):
    """Отсутствующий ключ → пустая строка (не KeyError)."""

    def __missing__(self, key: str) -> str:
        logger.debug("prompt var '%s' not provided → empty", key)
        return ""


def load_prompt(name: str) -> str:
    """Читает prompts/<name>.md (с кэшем)."""
    if name in _cache:
        return _cache[name]
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    text = path.read_text(encoding="utf-8")
    _cache[name] = text
    return text


def render_prompt(name: str, **variables) -> str:
    """Загружает промпт и подставляет переменные через {placeholder}.
    Отсутствующие плейсхолдеры → пустая строка (_SafeDict)."""
    template = load_prompt(name)
    try:
        return template.format_map(_SafeDict(variables))
    except (ValueError, IndexError) as e:
        # напр. одиночная { в тексте примера — не роняем весь вызов
        logger.warning("prompt '%s' format error: %s (returning raw)", name, e)
        return template


def format_rules_for(platform: str) -> str:
    """Правила форматирования платформы из config (раздел 3.1/14) как текст для промпта."""
    rules = settings.format_rules.get(platform)
    if not rules:
        available = ", ".join(settings.format_rules.keys())
        return f"(нет правил для платформы '{platform}'; известные: {available})"
    if isinstance(rules, dict):
        return "\n".join(f"- {k}: {v}" for k, v in rules.items())
    return str(rules)