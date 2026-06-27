from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

import config

logger = logging.getLogger(__name__)

# SQLite schema for local dev (Postgres version lives in db/schema.sql)
_SQLITE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS video_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id      INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    mode         TEXT NOT NULL DEFAULT 'lifestyle'
                     CHECK (mode IN ('lifestyle', 'talking')),
    scene_prompt TEXT,
    spoken_line  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    error        TEXT
);

CREATE INDEX IF NOT EXISTS idx_video_jobs_status_created
    ON video_jobs (status, created_at);
"""

_DB_PATH = Path("data/bot.db")


# ──────────────────────────────────────────────
# SQLite — локальная разработка
# ──────────────────────────────────────────────

class _SQLiteStore:
    async def init_db(self) -> None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.executescript(_SQLITE_SCHEMA)
            await db.commit()
        logger.info("Хранилище: SQLite (%s)", _DB_PATH)

    async def upsert_user(self, chat_id: int, username: str | None, first_name: str | None) -> None:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO users (chat_id, username, first_name, first_seen, last_seen)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(chat_id) DO UPDATE SET
                    username   = excluded.username,
                    first_name = excluded.first_name,
                    last_seen  = datetime('now')
                """,
                (chat_id, username, first_name),
            )
            await db.commit()

    async def save_message(self, chat_id: int, role: str, content: str, thread_id: int | None = None) -> None:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                "INSERT INTO messages (chat_id, thread_id, role, content) VALUES (?, ?, ?, ?)",
                (chat_id, thread_id, role, content),
            )
            await db.commit()

    async def get_history(self, chat_id: int, limit: int) -> list[dict]:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ORDER BY created_at ASC
                """,
                (chat_id, limit),
            )
            rows = await cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def reset_history(self, chat_id: int) -> None:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            await db.commit()

    async def get_stats(self) -> dict:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            users = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM messages")
            msgs = (await cursor.fetchone())[0]
            return {"users": users, "messages": msgs}

    async def enqueue_video_job(self, chat_id: int, mode: str, scene_prompt: str, spoken_line: str) -> int:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO video_jobs (chat_id, mode, scene_prompt, spoken_line) VALUES (?, ?, ?, ?)",
                (chat_id, mode, scene_prompt, spoken_line),
            )
            await db.commit()
            return cursor.lastrowid

    async def take_next_video_job(self) -> dict | None:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM video_jobs WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            job = dict(row)
            await db.execute(
                "UPDATE video_jobs SET status='processing', updated_at=datetime('now') WHERE id=?",
                (job["id"],),
            )
            await db.commit()
            return job

    async def update_video_job_status(self, job_id: int, status: str, error: str | None = None) -> None:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                "UPDATE video_jobs SET status=?, error=?, updated_at=datetime('now') WHERE id=?",
                (status, error, job_id),
            )
            await db.commit()

    async def fail_stale_jobs(self, older_than_minutes: int = 10) -> None:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                """UPDATE video_jobs SET status='failed', error='stale: restarted',
                   updated_at=datetime('now')
                   WHERE status='processing'
                   AND updated_at < datetime('now', ? || ' minutes')""",
                (f"-{older_than_minutes}",),
            )
            await db.commit()

    async def get_video_count_today(self, chat_id: int) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT video_count FROM daily_counters WHERE chat_id=? AND date=?",
                (chat_id, today),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def increment_video_count(self, chat_id: int) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                """INSERT INTO daily_counters (chat_id, date, video_count) VALUES (?, ?, 1)
                   ON CONFLICT(chat_id, date) DO UPDATE SET video_count = video_count + 1""",
                (chat_id, today),
            )
            await db.commit()


# ──────────────────────────────────────────────
# Supabase — продакшн (схема avatar_bot)
# ──────────────────────────────────────────────

class _SupabaseStore:
    def __init__(self, url: str, key: str) -> None:
        self._url = url
        self._key = key
        self._client = None

    async def _sb(self):
        """Ленивая инициализация клиента + переключение на схему avatar_bot."""
        if self._client is None:
            from supabase import acreate_client
            self._client = await acreate_client(self._url, self._key)
        return self._client.schema("avatar_bot")

    async def init_db(self) -> None:
        await self._sb()  # проверяем подключение
        logger.info("Хранилище: Supabase (проект kcfkhebtlyqgbzaajgiv, схема avatar_bot)")

    async def upsert_user(self, chat_id: int, username: str | None, first_name: str | None) -> None:
        sb = await self._sb()
        now = datetime.now(timezone.utc).isoformat()
        check = await sb.table("users").select("chat_id").eq("chat_id", chat_id).execute()
        if check.data:
            await sb.table("users").update({
                "username": username,
                "first_name": first_name,
                "last_seen": now,
            }).eq("chat_id", chat_id).execute()
        else:
            await sb.table("users").insert({
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
                "first_seen": now,
                "last_seen": now,
            }).execute()

    async def save_message(self, chat_id: int, role: str, content: str, thread_id: int | None = None) -> None:
        sb = await self._sb()
        await sb.table("messages").insert({
            "chat_id": chat_id,
            "thread_id": thread_id,
            "role": role,
            "content": content,
        }).execute()

    async def get_history(self, chat_id: int, limit: int) -> list[dict]:
        sb = await self._sb()
        resp = await (
            sb.table("messages")
            .select("role, content")
            .eq("chat_id", chat_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(resp.data)]

    async def reset_history(self, chat_id: int) -> None:
        sb = await self._sb()
        await sb.table("messages").delete().eq("chat_id", chat_id).execute()

    async def get_stats(self) -> dict:
        sb = await self._sb()
        users_resp = await sb.table("users").select("*", count="exact").execute()
        msgs_resp = await sb.table("messages").select("id", count="exact").execute()
        return {
            "users": users_resp.count or 0,
            "messages": msgs_resp.count or 0,
        }

    async def enqueue_video_job(self, chat_id: int, mode: str, scene_prompt: str, spoken_line: str) -> int:
        sb = await self._sb()
        resp = await sb.table("video_jobs").insert({
            "chat_id": chat_id,
            "mode": mode,
            "scene_prompt": scene_prompt,
            "spoken_line": spoken_line,
            "status": "queued",
        }).execute()
        return resp.data[0]["id"]

    async def take_next_video_job(self) -> dict | None:
        sb = await self._sb()
        resp = await (
            sb.table("video_jobs")
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        job = resp.data[0]
        now = datetime.now(timezone.utc).isoformat()
        await sb.table("video_jobs").update({"status": "processing", "updated_at": now}).eq("id", job["id"]).execute()
        return job

    async def update_video_job_status(self, job_id: int, status: str, error: str | None = None) -> None:
        sb = await self._sb()
        now = datetime.now(timezone.utc).isoformat()
        await sb.table("video_jobs").update({"status": status, "error": error, "updated_at": now}).eq("id", job_id).execute()

    async def fail_stale_jobs(self, older_than_minutes: int = 10) -> None:
        sb = await self._sb()
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        await (
            sb.table("video_jobs")
            .update({"status": "failed", "error": "stale: restarted", "updated_at": now})
            .eq("status", "processing")
            .lt("updated_at", cutoff)
            .execute()
        )

    async def get_video_count_today(self, chat_id: int) -> int:
        sb = await self._sb()
        today = datetime.now(timezone.utc).date().isoformat()
        resp = await sb.table("daily_counters").select("video_count").eq("chat_id", chat_id).eq("date", today).execute()
        return resp.data[0]["video_count"] if resp.data else 0

    async def increment_video_count(self, chat_id: int) -> None:
        sb = await self._sb()
        today = datetime.now(timezone.utc).date().isoformat()
        check = await sb.table("daily_counters").select("video_count").eq("chat_id", chat_id).eq("date", today).execute()
        if check.data:
            new_count = check.data[0]["video_count"] + 1
            await sb.table("daily_counters").update({"video_count": new_count}).eq("chat_id", chat_id).eq("date", today).execute()
        else:
            await sb.table("daily_counters").insert({"chat_id": chat_id, "date": today, "video_count": 1}).execute()


# ──────────────────────────────────────────────
# Публичный API модуля
# ──────────────────────────────────────────────

_store: _SQLiteStore | _SupabaseStore | None = None


async def init_db() -> None:
    global _store
    if config.SUPABASE_URL and config.SUPABASE_KEY:
        _store = _SupabaseStore(config.SUPABASE_URL, config.SUPABASE_KEY)
    else:
        _store = _SQLiteStore()
    await _store.init_db()


async def upsert_user(chat_id: int, username: str | None, first_name: str | None) -> None:
    await _store.upsert_user(chat_id, username, first_name)


async def save_message(chat_id: int, role: str, content: str, thread_id: int | None = None) -> None:
    await _store.save_message(chat_id, role, content, thread_id)


async def get_history(chat_id: int, limit: int) -> list[dict]:
    return await _store.get_history(chat_id, limit)


async def reset_history(chat_id: int) -> None:
    await _store.reset_history(chat_id)


async def get_stats() -> dict:
    return await _store.get_stats()


async def enqueue_video_job(chat_id: int, mode: str, scene_prompt: str, spoken_line: str) -> int:
    return await _store.enqueue_video_job(chat_id, mode, scene_prompt, spoken_line)


async def take_next_video_job() -> dict | None:
    return await _store.take_next_video_job()


async def update_video_job_status(job_id: int, status: str, error: str | None = None) -> None:
    await _store.update_video_job_status(job_id, status, error)


async def fail_stale_jobs(older_than_minutes: int = 10) -> None:
    await _store.fail_stale_jobs(older_than_minutes)


async def get_video_count_today(chat_id: int) -> int:
    return await _store.get_video_count_today(chat_id)


async def increment_video_count(chat_id: int) -> None:
    await _store.increment_video_count(chat_id)
