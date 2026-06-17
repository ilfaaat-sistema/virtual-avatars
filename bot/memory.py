from __future__ import annotations

import config
import db.store as store


async def get_history(chat_id: int) -> list[dict]:
    return await store.get_history(chat_id, config.HISTORY_MESSAGES)


async def save_turn(
    chat_id: int,
    user_text: str,
    assistant_text: str,
    thread_id: int | None = None,
) -> None:
    await store.save_message(chat_id, "user", user_text, thread_id)
    await store.save_message(chat_id, "assistant", assistant_text, thread_id)


async def reset(chat_id: int) -> None:
    await store.reset_history(chat_id)
