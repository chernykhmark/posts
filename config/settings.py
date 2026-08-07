# config/settings.py
"""Единый источник конфигурации проекта (см. дизайн-док, раздел 3.1)."""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelsSettings(BaseSettings):
    """Модели OpenRouter. Имена полей фиксированы дизайн-доком (3.1)."""

    model_config = SettingsConfigDict(env_prefix="MODEL_", extra="ignore")

    orchestrator: str = "openai/gpt-4.1-mini"          # tool calling
    generation: str = "openai/gpt-4.1-mini"            # make_angle / write_post / edit_post
    critique: str = "openai/gpt-4.1-mini"              # critique
    cheap: str = "openai/gpt-4.1-nano"                 # hashtags / analyze_style
    fallback_orchestrator: str = "anthropic/claude-3.5-haiku"  # ОБЯЗАН уметь tool calling


# Правила форматирования по платформам (дизайн-док, раздел 14).
# Эти же правила используются в code-проверках critique (длина, разметка).
FORMAT_RULES: dict[str, dict] = {
    "telegram": {
        "markup": "markdown",          # Markdown разрешен
        "max_length": 1500,            # ~1500 символов
        "emoji": True,
        "paragraphs": "blank_line",    # абзацы через пустую строку
        "hashtags": True,
    },
    "vk": {
        "markup": "none",              # чистый текст, без разметки
        "max_length": 4000,
        "emoji": True,
        "paragraphs": "blank_line",
        "links": "full_url",           # ссылки полным URL
        "hashtags": True,              # хэштеги через #
    },
}


class Settings(BaseSettings):
    """Корневые настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    # --- OpenRouter (ключ используется на будущих этапах) ---
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")

    # --- Postgres ---
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="postbot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postbot", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postbot", alias="POSTGRES_PASSWORD")

    # --- Модели ---
    models: ModelsSettings = Field(default_factory=ModelsSettings)

    # --- Typing-индикатор (раздел 8) ---
    typing_interval: int = Field(default=4, alias="TYPING_INTERVAL")

    # --- Thread-lock / конкурентность (раздел 7.1) ---
    concurrency_mode: Literal["queue", "reject"] = Field(default="queue", alias="CONCURRENCY_MODE")
    queue_size: int = Field(default=1, alias="QUEUE_SIZE")

    # --- Critique-цикл (раздел 4.3) ---
    critique_max_iterations: int = Field(default=2, alias="CRITIQUE_MAX_ITERATIONS")


    recent_posts_limit: int = 5  # последние N постов для защиты от дублей (раздел 10)

    # --- Форматирование платформ (раздел 14) ---
    format_rules: dict[str, dict] = Field(default_factory=lambda: FORMAT_RULES)

    # --- Логирование ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    @property
    def database_url(self) -> str:
        """DSN для asyncpg (этап 2)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()