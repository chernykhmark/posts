# agent/image_storage.py
"""Абстракция хранилища изображений (дизайн-док раздел 11, D-13).

ТОЛЬКО ИНТЕРФЕЙС. Реализация:
- v3: bytea в Postgres / локальный volume;
- v4: MinIO / S3.

Смена бэкенда не затрагивает логику графа.
"""
from abc import ABC, abstractmethod


class ImageStorage(ABC):
    """Хранилище байтов изображения. ref — внутренний ключ (posts.image_ref)."""

    @abstractmethod
    async def save(self, data: bytes, user_id: int | None = None) -> str:
        """Сохранить байты, вернуть ref (внутренний ключ)."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, ref: str) -> bytes:
        """Вернуть байты по ref."""
        raise NotImplementedError

    @abstractmethod
    async def url(self, ref: str) -> str:
        """Вернуть URL/ссылку на изображение по ref (если бэкенд её поддерживает)."""
        raise NotImplementedError