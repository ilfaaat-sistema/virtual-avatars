CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    thread_id  INTEGER,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created
    ON messages (chat_id, created_at);

CREATE TABLE IF NOT EXISTS daily_counters (
    chat_id     INTEGER NOT NULL,
    date        TEXT    NOT NULL,
    video_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, date)
);
