# agent/tools/__init__.py
"""Реестр инструментов оркестратора.

Оркестратор выбирает 8 инструментов (разделы 4.1, 5).
critique и attach_image НЕ регистрируются (внутри цикла / с v3).
"""

from agent.tools.style import analyze_style
from agent.tools.generation import make_angle, write_post, edit_post
from agent.tools.stubs import (
    generate_hooks_cta,
    generate_hashtags,
    get_history,
    save_post,
)

ORCHESTRATOR_TOOLS = [
    analyze_style,
    make_angle,
    write_post,
    edit_post,
    generate_hooks_cta,
    generate_hashtags,
    get_history,
    save_post,
]

TOOLS_BY_NAME = {t.name: t for t in ORCHESTRATOR_TOOLS}

__all__ = ["ORCHESTRATOR_TOOLS", "TOOLS_BY_NAME"]