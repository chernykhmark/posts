# agent/image_provider.py
"""Абстракция генератора изображений (дизайн-док раздел 11, D-13).

ТОЛЬКО ИНТЕРФЕЙС. Реализация — v4 (DALL·E / Imagen / Flux / Replicate).
OpenRouter = только текст; картинки идут через этот провайдер, не через LLM.
"""
from abc import ABC, abstractmethod


class ImageProvider(ABC):
    """Генерация изображения по текстовому промпту."""

    @abstractmethod
    async def generate(self, prompt: str, user_id: int | None = None) -> bytes:
        """Сгенерировать изображение по промпту, вернуть байты."""
        raise NotImplementedError