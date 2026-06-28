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

-- Учёт расходов провайдеров (для админ-команды /costs)
CREATE TABLE IF NOT EXISTS avatar_bot.usage_log (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    chat_id       BIGINT,
    provider      TEXT NOT NULL,            -- 'claude' | 'elevenlabs' | 'veo'
    in_tokens     BIGINT DEFAULT 0,
    out_tokens    BIGINT DEFAULT 0,
    cache_read    BIGINT DEFAULT 0,
    cache_write   BIGINT DEFAULT 0,
    chars         BIGINT DEFAULT 0,
    video_seconds NUMERIC DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_log_ts ON avatar_bot.usage_log (ts);

-- ──────────────────────────────────────────────────────────────────────────
-- ДОСТУП К DATA API (PostgREST). Без этого бот падает с
--   PGRST106 "Invalid schema: avatar_bot"
-- Бот ходит в БД серверным service_role-ключом. anon НЕ выдаём (RLS off).
GRANT USAGE ON SCHEMA avatar_bot TO service_role, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA avatar_bot TO service_role, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA avatar_bot TO service_role, authenticated;  -- BIGSERIAL id
ALTER DEFAULT PRIVILEGES IN SCHEMA avatar_bot
    GRANT ALL ON TABLES TO service_role, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA avatar_bot
    GRANT ALL ON SEQUENCES TO service_role, authenticated;

-- ВАЖНО: помимо GRANT'ов схему нужно ВКЛЮЧИТЬ в Data API, иначе PGRST106:
--   Dashboard → Project Settings → API → Exposed schemas → добавить avatar_bot → Save.
-- (Эквивалент в SQL, но менее durable — может сброситься при ребуте платформы:
--   ALTER ROLE authenticator SET pgrst.db_schemas = 'public, graphql_public, avatar_bot';
--   NOTIFY pgrst, 'reload config'; )
