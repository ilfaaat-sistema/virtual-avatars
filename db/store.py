from __future__ import annotations

import aiosqlite
from pathlib import Path

DB_PATH = Path("data/bot.db")


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        await db.commit()


async def upsert_user(chat_id: int, username: str | None, first_name: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
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


async def save_message(
    chat_id: int, role: str, content: str, thread_id: int | None = None
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, thread_id, role, content) VALUES (?, ?, ?, ?)",
            (chat_id, thread_id, role, content),
        )
        await db.commit()


async def get_history(chat_id: int, limit: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
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
        return [{"role": row["role"], "content": row["content"]} for row in rows]


async def reset_history(chat_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        msg_count = (await cursor.fetchone())[0]
        return {"users": user_count, "messages": msg_count}
