
-- Идемпотентная миграция MVP-таблиц (раздел 15). Только финальные данные и затраты.
-- Память диалога живет отдельно (LangGraph checkpointer), здесь ее нет.

CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    auto_mode   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS style_profiles (
    user_id           BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    style_description  TEXT NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS posts (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    topic      TEXT,
    angle      TEXT,
    text       TEXT NOT NULL,
    hooks_cta  JSONB,
    hashtags   JSONB,
    image_ref  TEXT,
    platform   TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_posts_user_created
    ON posts (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS usage_costs (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    model      TEXT NOT NULL,
    tokens_in  INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost       NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_costs_user_created
    ON usage_costs (user_id, created_at DESC);