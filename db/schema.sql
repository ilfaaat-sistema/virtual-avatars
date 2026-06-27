-- Схема Postgres для Supabase (проект kcfkhebtlyqgbzaajgiv, схема avatar_bot)
-- Применяется через MCP-миграцию. SQLite-версия встроена в db/store.py.

CREATE SCHEMA IF NOT EXISTS avatar_bot;

CREATE TABLE IF NOT EXISTS avatar_bot.users (
    chat_id    BIGINT PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS avatar_bot.messages (
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT NOT NULL,
    thread_id  BIGINT,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created
    ON avatar_bot.messages (chat_id, created_at);

CREATE TABLE IF NOT EXISTS avatar_bot.daily_counters (
    chat_id     BIGINT NOT NULL,
    date        DATE NOT NULL,
    video_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, date)
);

CREATE TABLE IF NOT EXISTS avatar_bot.video_jobs (
    id           BIGSERIAL PRIMARY KEY,
    chat_id      BIGINT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    mode         TEXT NOT NULL DEFAULT 'lifestyle'
                     CHECK (mode IN ('lifestyle', 'talking')),
    scene_prompt TEXT,
    spoken_line  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    error        TEXT
);

CREATE INDEX IF NOT EXISTS idx_video_jobs_status_created
    ON avatar_bot.video_jobs (status, created_at);
