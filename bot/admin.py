import logging
from functools import wraps

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, Document

import config
import db.store as store
from bot import persona_kb

logger = logging.getLogger(__name__)
router = Router()


def admin_only(handler):
    @wraps(handler)
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user and message.from_user.id == config.ADMIN_TELEGRAM_ID:
            return await handler(message, *args, **kwargs)
        await message.answer("Нет доступа.")
    return wrapper


@router.message(Command("reload_kb"))
@admin_only
async def cmd_reload_kb(message: Message) -> None:
    persona_kb.load()
    await message.answer("КБ перезагружена.")


@router.message(Command("kb"))
@admin_only
async def cmd_kb(message: Message) -> None:
    files = persona_kb.list_files()
    text = (
        "Файлы в knowledge/:\n" + "\n".join(f"• {f}" for f in files)
        if files
        else "knowledge/ пуст или не найден."
    )
    await message.answer(text)


@router.message(Command("persona"))
@admin_only
async def cmd_persona(message: Message) -> None:
    text = persona_kb.get_persona()
    if len(text) > 4000:
        text = text[:4000] + "\n\n[обрезано]"
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")


@router.message(Command("stats"))
@admin_only
async def cmd_stats(message: Message) -> None:
    stats = await store.get_stats()
    await message.answer(
        f"Пользователей: {stats['users']}\nСообщений: {stats['messages']}"
    )


@router.message(Command("reset_chat"))
@admin_only
async def cmd_reset_chat(message: Message) -> None:
    await store.reset_history(message.chat.id)
    await message.answer("История этого чата удалена.")


@router.message(lambda m: m.document is not None)
@admin_only
async def handle_document(message: Message) -> None:
    doc: Document = message.document
    if not (doc.file_name.endswith(".md") or doc.file_name.endswith(".txt")):
        await message.answer("Принимаю только .md и .txt файлы.")
        return

    config.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.KNOWLEDGE_DIR / doc.file_name
    await message.bot.download(doc, destination=dest)
    persona_kb.load()
    await message.answer(
        f"Файл {doc.file_name} сохранён в knowledge/ и КБ перезагружена."
    )
